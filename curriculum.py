"""Curriculum-design view of skill demand: skill bundles and occupation-transition gaps.

    python -m src.analysis.curriculum                   # pilot: chunks 0-5
    python -m src.analysis.curriculum --preset full     # after the full run

(A) Skill bundling — which skills belong in one course
    1. RCA of every skill in every occupation group (share in group / share overall).
    2. Co-occurrence network over the top-N skills, edges weighted by PMI (or lift),
       weak edges dropped, Louvain communities = candidate course bundles.
    3. Stability of the partition across Louvain seeds (mean pairwise ARI / NMI).
(B) Occupation-transition skill gaps (simplified after Dawson et al. 2021)
    1. Occupation-group skill vectors (posting shares, and an RCA-weighted variant).
    2. Pairwise cosine similarity between groups.
    3. For every ordered pair A→B: skills to add (share_B - share_A) and transferable skills.
    4. Optional finer similarity between the top search_position terms.

Reads the row-level pipeline output strictly read-only (same inputs and conventions as
build_summaries: one posting per dup_group_id, generic / "(unspecified)" skills excluded).
Writes CSV tables to <summary-dir>/curriculum/ (read by the Streamlit app) and a markdown report.
"""

from __future__ import annotations

import argparse
import json
import resource
import sys
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score

from src.analysis.build_summaries import connect
from src.analysis.config import QUALITY, QUALITY_NOTE, ROOT, add_input_args, resolve_inputs

# ---- defaults; every one of these is also a CLI argument --------------------------------
SEED = 42
STABILITY_SEEDS = [0, 1, 2, 3, 4]     # Louvain seeds compared for partition stability
TOP_SKILLS = 300                      # nodes in the co-occurrence network (by postings)
MIN_SKILL_JOBS = 100                  # a network skill must appear in at least this many postings
MIN_LIFT = 1.5                        # keep an edge only if lift > MIN_LIFT ...
MIN_CO_JOBS = 30                      # ... and the pair co-occurs in at least this many postings
EDGE_WEIGHT = "pmi"                   # "pmi" (log2 lift, positive by construction) or "lift"
RESOLUTION = 1.5                      # Louvain resolution (higher -> more, smaller communities)
RESOLUTION_GRID = [1.0, 1.5, 2.0]     # resolutions compared in the report's sensitivity table
RCA_MIN = 1.0                         # RCA table keeps skills with RCA > RCA_MIN
RCA_MIN_GROUP_JOBS = 20               # ... and at least this many postings in the group
VEC_MIN_SKILL_JOBS = 50               # skills used in occupation vectors (overall postings)
GAP_MIN_SHARE_TO = 0.03               # gap skills must reach this share in the target group
TRANSFER_MIN_SHARE = 0.05             # transferable skills must reach this share on both sides
TOP_GAP = 15                          # skills kept per ordered pair
TOP_POSITIONS = 50                    # search_position terms in the finer similarity (0 = skip)
OTHER_GROUP = "Other"                 # catch-all group, left out of group-level tables by default


# ---------------------------------------------------------------------------------- core maths
def rca_matrix(counts: np.ndarray, n_group: np.ndarray, n_total: int,
               skill_total: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Revealed comparative advantage on posting shares.

    counts[g, s] = postings in group g mentioning skill s; n_group[g] = postings in g;
    n_total = all postings (the denominator of the overall share). ``skill_total`` is the
    overall posting count per skill (defaults to the column sums of ``counts``).
    Returns (rca, share_group, share_overall); RCA is 0 where the skill never occurs.
    """
    counts = np.asarray(counts, dtype=float)
    share_g = counts / np.asarray(n_group, dtype=float)[:, None]
    tot = counts.sum(axis=0) if skill_total is None else np.asarray(skill_total, dtype=float)
    share_all = tot / float(n_total)
    rca = np.divide(share_g, share_all[None, :], out=np.zeros_like(share_g), where=share_all[None, :] > 0)
    return rca, share_g, share_all


def cosine_matrix(V: np.ndarray) -> np.ndarray:
    """Pairwise cosine similarity between the rows of V."""
    V = np.asarray(V, dtype=float)
    norm = np.linalg.norm(V, axis=1, keepdims=True)
    U = np.divide(V, norm, out=np.zeros_like(V), where=norm > 0)
    return np.clip(U @ U.T, 0.0, 1.0)


def skill_gaps(share_from: np.ndarray, share_to: np.ndarray, skills, min_share_to: float = GAP_MIN_SHARE_TO,
               top_n: int = TOP_GAP) -> pd.DataFrame:
    """Skills to add when moving from A to B: common in B, rarer in A. gap = share_to - share_from."""
    d = pd.DataFrame({"skill": np.asarray(skills), "share_from": share_from, "share_to": share_to})
    d["gap"] = d.share_to - d.share_from
    d = d[(d.share_to >= min_share_to) & (d.gap > 0)].sort_values(["gap", "skill"], ascending=[False, True]).head(top_n)
    d["rank"] = np.arange(1, len(d) + 1)
    return d.reset_index(drop=True)


def transferable_skills(share_from: np.ndarray, share_to: np.ndarray, skills,
                        min_share: float = TRANSFER_MIN_SHARE, top_n: int = TOP_GAP) -> pd.DataFrame:
    """Skills common on both sides of a transition, ranked by the smaller of the two shares."""
    d = pd.DataFrame({"skill": np.asarray(skills), "share_from": share_from, "share_to": share_to})
    d["share_min"] = d[["share_from", "share_to"]].min(axis=1)
    d = d[d.share_min >= min_share].sort_values(["share_min", "skill"], ascending=[False, True]).head(top_n)
    d["rank"] = np.arange(1, len(d) + 1)
    return d.reset_index(drop=True)


def cooccurrence_edges(co: np.ndarray, n_skill: np.ndarray, n_total: int, skills, min_lift: float = MIN_LIFT,
                       min_co: int = MIN_CO_JOBS, weight: str = EDGE_WEIGHT) -> pd.DataFrame:
    """Edge list from a skill x skill co-occurrence count matrix, weak edges removed."""
    co = np.asarray(co, dtype=float)
    n_skill = np.asarray(n_skill, dtype=float)
    a, b = np.triu_indices(len(n_skill), k=1)
    n_co = co[a, b]
    lift = n_co * float(n_total) / (n_skill[a] * n_skill[b])
    keep = (lift > min_lift) & (n_co >= min_co)
    a, b, n_co, lift = a[keep], b[keep], n_co[keep], lift[keep]
    skills = np.asarray(skills)
    e = pd.DataFrame({"skill_a": skills[a], "skill_b": skills[b], "n_co": n_co.astype(int),
                      "lift": lift, "pmi": np.log2(lift)})
    e["weight"] = e["pmi"] if weight == "pmi" else e["lift"]
    return e.sort_values("weight", ascending=False).reset_index(drop=True)


def build_graph(edges: pd.DataFrame) -> nx.Graph:
    G = nx.Graph()
    # sorted insertion keeps Louvain reproducible for a given seed
    for r in edges.sort_values(["skill_a", "skill_b"]).itertuples():
        G.add_edge(r.skill_a, r.skill_b, weight=float(r.weight))
    return G


def louvain_partition(G: nx.Graph, seed: int = SEED, resolution: float = RESOLUTION) -> dict[str, int]:
    """skill -> community id (1 = largest community; ties broken alphabetically)."""
    comms = nx.community.louvain_communities(G, weight="weight", resolution=resolution, seed=seed)
    comms = sorted((sorted(c) for c in comms), key=lambda c: (-len(c), c[0]))
    return {s: i for i, c in enumerate(comms, start=1) for s in c}


def partition_stability(G: nx.Graph, seeds=STABILITY_SEEDS, resolution: float = RESOLUTION) -> dict:
    """Mean pairwise ARI / NMI between Louvain partitions obtained with different seeds."""
    nodes = sorted(G.nodes)
    parts = [louvain_partition(G, s, resolution) for s in seeds]
    labels = [[p[n] for n in nodes] for p in parts]
    pairs = list(combinations(range(len(seeds)), 2))
    ari = [adjusted_rand_score(labels[i], labels[j]) for i, j in pairs]
    nmi = [normalized_mutual_info_score(labels[i], labels[j]) for i, j in pairs]
    return {"seeds": list(seeds), "n_communities": [len(set(l)) for l in labels],
            "ari_mean": float(np.mean(ari)) if ari else 1.0, "ari_min": float(np.min(ari)) if ari else 1.0,
            "nmi_mean": float(np.mean(nmi)) if nmi else 1.0, "nmi_min": float(np.min(nmi)) if nmi else 1.0}


def describe_communities(G: nx.Graph, part: dict[str, int], seed: int = SEED) -> pd.DataFrame:
    """One row per skill: community, centrality inside the community, layout coordinates."""
    pos = nx.spring_layout(G, weight="weight", seed=seed, iterations=60)
    global_dc = nx.degree_centrality(G)
    rows = []
    for cid in sorted(set(part.values())):
        members = [n for n in G.nodes if part[n] == cid]
        sub = G.subgraph(members)
        dc = nx.degree_centrality(sub) if len(members) > 1 else {members[0]: 0.0}
        for n in members:
            rows.append({"community_id": cid, "skill": n, "degree_centrality": dc[n],
                         "intra_strength": sub.degree(n, weight="weight"), "intra_degree": sub.degree(n),
                         "degree_centrality_global": global_dc[n], "x": pos[n][0], "y": pos[n][1]})
    d = pd.DataFrame(rows).sort_values(["community_id", "degree_centrality", "intra_strength", "skill"],
                                       ascending=[True, False, False, True])
    d["rank"] = d.groupby("community_id").cumcount() + 1
    return d.reset_index(drop=True)


# ---------------------------------------------------------------------------------- data access
def load_matrix(inp: dict):
    """Deduplicated postings x specific skills, binary CSR.

    Returns (X, jobs, skills): jobs has one row per deduplicated posting (also postings
    without any specific skill, so shares use the same denominators as build_summaries);
    skills is ordered by posting count, descending.
    """
    con = connect(inp)
    con.execute("""CREATE TEMP TABLE jdim AS
                   SELECT job_link, position_group, search_position,
                          row_number() OVER (ORDER BY job_link) - 1 AS j FROM jobs""")
    con.execute("""CREATE TEMP TABLE sdim AS
                   SELECT skill, count(DISTINCT job_link) AS n_jobs,
                          row_number() OVER (ORDER BY count(DISTINCT job_link) DESC, skill) - 1 AS s
                   FROM sk WHERE NOT generic GROUP BY 1""")
    jobs = con.execute("SELECT position_group, search_position FROM jdim ORDER BY j").df()
    skills = con.execute("SELECT skill, n_jobs FROM sdim ORDER BY s").df()
    long = con.execute("""SELECT DISTINCT d.j::INTEGER AS j, m.s::INTEGER AS s
                          FROM sk JOIN jdim d USING (job_link) JOIN sdim m USING (skill)
                          WHERE NOT sk.generic""").fetchnumpy()
    con.close()
    for c in ("position_group", "search_position"):
        jobs[c] = jobs[c].fillna("(missing)").astype("category")
    X = sparse.csr_matrix((np.ones(len(long["j"]), dtype=np.int32), (long["j"], long["s"])),
                          shape=(len(jobs), len(skills)))
    return X, jobs, skills


def group_counts(X: sparse.csr_matrix, labels: pd.Series) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Postings per (label, skill) and postings per label, via a sparse indicator product."""
    cat = labels.astype("category")
    names = [str(c) for c in cat.cat.categories]
    codes = cat.cat.codes.to_numpy()
    ind = sparse.csr_matrix((np.ones(len(codes), dtype=np.int32), (codes, np.arange(len(codes)))),
                            shape=(len(names), len(codes)))
    return np.asarray((ind @ X).todense()), np.bincount(codes, minlength=len(names)), names


# ---------------------------------------------------------------------------------- analyses
def run_bundles(X, jobs, skills, p: dict) -> dict:
    n_total = X.shape[0]
    counts, n_group, groups = group_counts(X, jobs.position_group)
    skill_n = skills.n_jobs.to_numpy()
    rca, share_g, share_all = rca_matrix(counts, n_group, n_total, skill_n)
    keep_g = [i for i, g in enumerate(groups) if p["include_other"] or g != OTHER_GROUP]

    # A1 — RCA table
    parts = []
    for i in keep_g:
        m = (rca[i] > p["rca_min"]) & (counts[i] >= p["rca_min_group_jobs"])
        d = pd.DataFrame({"position_group": groups[i], "skill": skills.skill[m], "n_jobs": counts[i][m].astype(int),
                          "share_group": share_g[i][m], "share_overall": share_all[m], "rca": rca[i][m]})
        d = d.sort_values(["rca", "n_jobs"], ascending=False)
        d["rank"] = np.arange(1, len(d) + 1)
        parts.append(d)
    rca_tab = pd.concat(parts, ignore_index=True)

    # A2 — co-occurrence network over the top skills (skills are already sorted by postings)
    n_top = int(min(p["top_skills"], (skill_n >= p["min_skill_jobs"]).sum()))
    Xt = X[:, :n_top].tocsc()
    co = np.asarray((Xt.T @ Xt).todense())
    top_names = skills.skill.to_numpy()[:n_top]
    edges = cooccurrence_edges(co, skill_n[:n_top], n_total, top_names, p["min_lift"], p["min_co_jobs"], p["edge_weight"])
    G = build_graph(edges)
    part = louvain_partition(G, p["seed"], p["resolution"])
    members = describe_communities(G, part, p["seed"])
    members = members.merge(skills.assign(share_jobs=skills.n_jobs / n_total), on="skill")
    members = members.sort_values(["community_id", "rank"]).reset_index(drop=True)
    edges["community_a"], edges["community_b"] = edges.skill_a.map(part), edges.skill_b.map(part)
    modularity = nx.community.modularity(G, [{n for n in G if part[n] == c} for c in sorted(set(part.values()))],
                                         weight="weight", resolution=p["resolution"])

    # coverage: share of a group's postings that mention at least one / two skills of the community
    sidx = pd.Series(np.arange(len(skills)), index=skills.skill)
    codes = jobs.position_group.cat.codes.to_numpy()
    cov, summary = [], []
    for cid, d in members.groupby("community_id"):
        hits = np.asarray(X[:, sidx.loc[d.skill].to_numpy()].sum(axis=1)).ravel()
        any1, any2 = hits >= 1, hits >= 2
        rows = [{"community_id": cid, "position_group": "ALL", "n_jobs_in_group": n_total,
                 "coverage_any": any1.mean(), "coverage_2plus": any2.mean()}]
        for i in keep_g:
            m = codes == i
            rows.append({"community_id": cid, "position_group": groups[i], "n_jobs_in_group": int(m.sum()),
                         "coverage_any": any1[m].mean(), "coverage_2plus": any2[m].mean()})
        cov.extend(rows)
        best = max(rows[1:], key=lambda r: r["coverage_any"])
        intra = edges[(edges.community_a == cid) & (edges.community_b == cid)]
        summary.append({"community_id": cid, "name": " · ".join(d.skill.head(3)), "size": len(d),
                        "n_edges_intra": len(intra), "coverage_all": rows[0]["coverage_any"],
                        "top_group": best["position_group"], "top_group_coverage": best["coverage_any"],
                        "members": "; ".join(d.skill)})
    stab = partition_stability(G, p["stability_seeds"], p["resolution"])
    sens = [{"resolution": r, **{k: v for k, v in partition_stability(G, p["stability_seeds"], r).items() if k != "seeds"}}
            for r in p["resolution_grid"]]
    return {"rca": rca_tab, "edges": edges, "members": members, "coverage": pd.DataFrame(cov),
            "communities": pd.DataFrame(summary), "stability": stab, "sensitivity": sens,
            "network": {"n_candidate_skills": n_top, "n_nodes": G.number_of_nodes(), "n_edges": G.number_of_edges(),
                        "n_isolated_dropped": n_top - G.number_of_nodes(), "modularity": float(modularity),
                        "n_communities": int(len(summary))},
            "_group": (counts, n_group, groups, rca, share_g, keep_g)}


def run_transitions(X, jobs, skills, p: dict, group_stats) -> dict:
    counts, n_group, groups, rca, share_g, keep_g = group_stats
    names = [groups[i] for i in keep_g]
    vec = skills.n_jobs.to_numpy() >= p["vec_min_skill_jobs"]
    S = share_g[keep_g][:, vec]
    W = S * rca[keep_g][:, vec]          # RCA-weighted: up-weights skills distinctive for the group
    cos_s, cos_r = cosine_matrix(S), cosine_matrix(W)
    sim = pd.DataFrame([{"from": a, "to": b, "cosine_share": cos_s[i, j], "cosine_rca": cos_r[i, j]}
                        for i, a in enumerate(names) for j, b in enumerate(names)])
    sk = skills.skill.to_numpy()
    gaps, trans = [], []
    for i, a in zip(keep_g, names):
        for j, b in zip(keep_g, names):
            if i == j:
                continue
            g = skill_gaps(share_g[i], share_g[j], sk, p["gap_min_share_to"], p["top_gap"])
            g.insert(0, "to", b), g.insert(0, "from", a)
            gaps.append(g)
            t = transferable_skills(share_g[i], share_g[j], sk, p["transfer_min_share"], p["top_gap"])
            t.insert(0, "to", b), t.insert(0, "from", a)
            trans.append(t)
    # how much of each group comes from its two largest search terms (flags narrow groups)
    pos_n = jobs.groupby(["position_group", "search_position"], observed=True).size()
    conc = {g: {"top_terms": pos_n[g].nlargest(2).index.astype(str).tolist(),
                "top2_share": float(pos_n[g].nlargest(2).sum() / pos_n[g].sum())} for g in names}
    out = {"similarity": sim, "matrix_share": pd.DataFrame(cos_s, index=names, columns=names),
           "matrix_rca": pd.DataFrame(cos_r, index=names, columns=names),
           "gaps": pd.concat(gaps, ignore_index=True), "transferable": pd.concat(trans, ignore_index=True),
           "group_sizes": {g: int(n_group[i]) for i, g in zip(keep_g, names)}, "n_vector_skills": int(vec.sum()),
           "group_concentration": conc}

    # B4 — finer view: top search_position terms (same vectors, more rows)
    out["positions"] = None
    if p["top_positions"] > 0:
        top = jobs.search_position.value_counts().head(p["top_positions"])
        lab = jobs.search_position.astype(object).where(jobs.search_position.isin(top.index), "(rest)")
        pc, pn, pnames = group_counts(X, lab)
        keep = [i for i, n in enumerate(pnames) if n != "(rest)"]
        ps = (pc[keep] / pn[keep][:, None])[:, vec]
        pcos = cosine_matrix(ps)
        pnames = [pnames[i] for i in keep]
        grp = jobs.groupby("search_position", observed=True).position_group.agg(lambda s: s.mode().iat[0])
        out["positions"] = pd.DataFrame(
            [{"position_a": a, "position_b": b, "cosine_share": pcos[i, j], "n_jobs_a": int(top[a]),
              "n_jobs_b": int(top[b]), "group_a": str(grp[a]), "group_b": str(grp[b])}
             for i, a in enumerate(pnames) for j, b in enumerate(pnames)])
    return out


# ---------------------------------------------------------------------------------- report
def _pairs(sim: pd.DataFrame, col: str) -> pd.DataFrame:
    return sim[sim["from"] < sim["to"]].sort_values(col, ascending=False)


def write_report(path: Path, meta: dict, b: dict, t: dict) -> None:
    p, net, stab = meta["params"], meta["network"], meta["stability"]
    L = ["# Curriculum insights: skill bundles and occupation-transition gaps", "",
         f"Source: `{meta['source']}` — {meta['n_postings_dedup']:,} deduplicated postings, "
         f"{meta['n_skills']:,} specific skills. Generated {meta['generated_at_utc']}.", "",
         "Reproduce with `python -m src.analysis.curriculum` (add `--preset full` after the full run). "
         "Tables are in `" + meta["out_dir"] + "/`.", "",
         "## Method", "",
         "- **Unit and filters.** One posting per `dup_group_id`; generic and `(unspecified)` skill labels are "
         "excluded. Shares are shares of deduplicated postings (postings without any skill stay in the denominator).",
         f"- **RCA.** RCA(s, g) = share of postings in group g that mention s ÷ share of all postings that mention s. "
         f"The table keeps RCA > {p['rca_min']:g} with at least {p['rca_min_group_jobs']} postings in the group.",
         f"- **Co-occurrence network.** Nodes: the top {p['top_skills']} skills by postings (each in ≥ {p['min_skill_jobs']} "
         f"postings). Edge between two skills if lift > {p['min_lift']:g} and they co-occur in ≥ {p['min_co_jobs']} postings; "
         f"edge weight = {'PMI = log2(lift)' if p['edge_weight'] == 'pmi' else 'lift'}. "
         f"Communities: Louvain (networkx, resolution {p['resolution']:g}, seed {p['seed']}). "
         "A community is named after its three members with the highest within-community degree centrality.",
         "- **Coverage.** Share of a group's postings that mention at least one skill of the community.",
         f"- **Stability.** Louvain re-run with seeds {stab['seeds']}; mean pairwise ARI and NMI between the partitions.",
         f"- **Occupation vectors.** Posting share of each skill with ≥ {p['vec_min_skill_jobs']} postings overall "
         f"({meta['n_vector_skills']:,} skills); the RCA-weighted variant multiplies each share by the skill's RCA in "
         "that group. Similarity is the cosine between two vectors.",
         f"- **Transition A→B.** Skills to add: share_B ≥ {p['gap_min_share_to']:.0%}, ranked by gap = share_B − share_A "
         f"(top {p['top_gap']}). Transferable skills: share ≥ {p['transfer_min_share']:.0%} in both groups, ranked by the "
         "smaller share.",
         f"- The catch-all group `{OTHER_GROUP}` is {'included' if p['include_other'] else 'left out of group-level tables (its postings still count in overall shares)'}.",
         "", "## A. Skill bundles", "",
         f"The network has {net['n_nodes']} skills and {net['n_edges']:,} edges "
         f"({net['n_isolated_dropped']} of the {net['n_candidate_skills']} candidate skills have no edge above the "
         f"thresholds and are left out). Louvain finds **{net['n_communities']} communities** "
         f"(modularity {net['modularity']:.2f}).", "",
         f"**Stability across {len(stab['seeds'])} seeds:** mean ARI {stab['ari_mean']:.3f} (min {stab['ari_min']:.3f}), "
         f"mean NMI {stab['nmi_mean']:.3f} (min {stab['nmi_min']:.3f}); communities per seed: {stab['n_communities']}.", "",
         "Sensitivity to the Louvain resolution (same graph, same seeds):", "",
         "| Resolution | Communities per seed | Mean ARI | Mean NMI |", "|---|---|---|---|",
         *[f"| {r['resolution']:g}{' (used)' if r['resolution'] == p['resolution'] else ''} | {r['n_communities']} | "
           f"{r['ari_mean']:.3f} | {r['nmi_mean']:.3f} |" for r in meta["sensitivity"]], "",
         "| # | Community (top-3 central skills) | Skills | Postings covered | Strongest group (coverage) | Members (by centrality, first 10) |",
         "|---|---|---|---|---|---|"]
    for r in b["communities"].itertuples():
        mem = r.members.split("; ")
        L.append(f"| {r.community_id} | {r.name} | {r.size} | {r.coverage_all:.1%} | "
                 f"{r.top_group.replace('_', ' ')} ({r.top_group_coverage:.1%}) | "
                 f"{', '.join(mem[:10])}{' …' if len(mem) > 10 else ''} |")
    L += ["", "### Most distinctive skills per occupation group (top 8 by RCA)", "",
          "| Occupation group | Skills (RCA) |", "|---|---|"]
    for g, d in b["rca"].groupby("position_group"):
        L.append(f"| {g.replace('_', ' ')} | " + ", ".join(f"{r.skill} ({r.rca:.1f})" for r in d.head(8).itertuples()) + " |")

    sim = t["similarity"]
    L += ["", "## B. Occupation transitions", "",
          f"Cosine similarity between the {len(t['group_sizes'])} occupation groups (posting-share vectors):", ""]
    m = t["matrix_share"]
    short = [c.replace("_", " ") for c in m.columns]
    L += ["| | " + " | ".join(short) + " |", "|---|" + "---|" * len(short)]
    L += [f"| {short[i]} | " + " | ".join(f"{v:.2f}" for v in row) + " |" for i, row in enumerate(m.to_numpy())]
    for col, label in (("cosine_share", "posting-share vectors"), ("cosine_rca", "RCA-weighted vectors")):
        pr = _pairs(sim, col)
        fmt = lambda d: "; ".join(f"{r['from'].replace('_', ' ')} ↔ {r['to'].replace('_', ' ')} ({r[col]:.2f})"  # noqa: E731
                                  for _, r in d.iterrows())
        L += ["", f"**{label.capitalize()}** — most similar: {fmt(pr.head(3))}. Least similar: {fmt(pr.tail(3).iloc[::-1])}."]
    top = _pairs(sim, "cosine_share").iloc[0]
    for a, bb in ((top["from"], top["to"]), (top["to"], top["from"])):
        g = t["gaps"][(t["gaps"]["from"] == a) & (t["gaps"]["to"] == bb)]
        tr = t["transferable"][(t["transferable"]["from"] == a) & (t["transferable"]["to"] == bb)]
        L += ["", f"### Example: {a.replace('_', ' ')} → {bb.replace('_', ' ')}", "",
              "| Rank | Skill to add | Share in origin | Share in target | Gap |", "|---|---|---|---|---|"]
        L += [f"| {r.rank} | {r.skill} | {r.share_from:.1%} | {r.share_to:.1%} | +{r.gap:.1%} |" for r in g.itertuples()]
        L += ["", "Transferable: " + (", ".join(f"{r.skill} ({r.share_from:.0%} / {r.share_to:.0%})"
                                                for r in tr.itertuples()) or "none above the threshold") + "."]
    if t["positions"] is not None:
        pp = t["positions"]
        pp = pp[pp.position_a < pp.position_b].sort_values("cosine_share", ascending=False)
        L += ["", f"### Finer view: top {meta['params']['top_positions']} search-position terms", "",
              "Most similar pairs of position terms (posting-share vectors):", "",
              "| Position A | Position B | Cosine |", "|---|---|---|"]
        L += [f"| {r.position_a} | {r.position_b} | {r.cosine_share:.2f} |" for r in pp.head(10).itertuples()]
    L += ["", "## Limitations", "",
          f"- **Skill extraction quality.** Precision ≈ {QUALITY['skill_precision']:.2f}, recall ≈ {QUALITY['skill_recall']:.2f} "
          "on 50 unseen postings. Roughly one extracted skill in three is wrong, so rare co-occurrences and small "
          "gaps are noisy; read rankings and bundles, not individual percentages.",
          f"- **Sample.** {meta['sample_note']}",
          "- **Narrow groups.** Some occupation groups are dominated by one or two search terms in this data, so their "
          "profile is the profile of those terms: " + ("; ".join(
              f"{g.replace('_', ' ')} ({' + '.join(c['top_terms'])} = {c['top2_share']:.0%})"
              for g, c in meta["group_concentration"].items() if c["top2_share"] >= 0.5) or "none above 50%") + ".",
          "- **Co-occurrence is not prerequisite structure.** Two skills in one community are requested together by "
          "employers; that says nothing about teaching order or dependency between them.",
          "- **Shares, not importance.** A gap is a difference in how often postings mention a skill, not in the "
          "depth required. Occupation groups are broad and keyed on the LinkedIn search term, not the job content.",
          "- **Thresholds matter.** The number of communities depends on the edge filters and the Louvain resolution; "
          "the stability figures above cover seed variation only.", ""]
    path.write_text("\n".join(L))


# ---------------------------------------------------------------------------------- CLI
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_input_args(ap)
    ap.add_argument("--top-skills", type=int, default=TOP_SKILLS, help="skills in the co-occurrence network")
    ap.add_argument("--min-skill-jobs", type=int, default=MIN_SKILL_JOBS, help="min postings for a network skill")
    ap.add_argument("--min-lift", type=float, default=MIN_LIFT)
    ap.add_argument("--min-co-jobs", type=int, default=MIN_CO_JOBS, help="min co-occurring postings per edge")
    ap.add_argument("--edge-weight", choices=["pmi", "lift"], default=EDGE_WEIGHT)
    ap.add_argument("--resolution", type=float, default=RESOLUTION)
    ap.add_argument("--resolution-grid", type=float, nargs="+", default=RESOLUTION_GRID)
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--stability-seeds", type=int, nargs="+", default=STABILITY_SEEDS)
    ap.add_argument("--rca-min", type=float, default=RCA_MIN)
    ap.add_argument("--rca-min-group-jobs", type=int, default=RCA_MIN_GROUP_JOBS)
    ap.add_argument("--vec-min-skill-jobs", type=int, default=VEC_MIN_SKILL_JOBS)
    ap.add_argument("--gap-min-share-to", type=float, default=GAP_MIN_SHARE_TO)
    ap.add_argument("--transfer-min-share", type=float, default=TRANSFER_MIN_SHARE)
    ap.add_argument("--top-gap", type=int, default=TOP_GAP)
    ap.add_argument("--top-positions", type=int, default=TOP_POSITIONS, help="0 skips the position-term view")
    ap.add_argument("--include-other", action="store_true", help=f"keep the catch-all {OTHER_GROUP} group")
    ap.add_argument("--report", type=Path, help="default: outputs/curriculum_report.md (pilot) / _full.md (full)")
    args = ap.parse_args(argv)
    inp = resolve_inputs(args)
    out = Path(inp["summary_dir"]) / "curriculum"
    out.mkdir(parents=True, exist_ok=True)
    report = args.report or ROOT / "outputs" / ("curriculum_report.md" if args.preset == "pilot" else f"curriculum_report_{args.preset}.md")
    p = {k: getattr(args, k) for k in ("top_skills", "min_skill_jobs", "min_lift", "min_co_jobs", "edge_weight",
                                       "resolution", "resolution_grid", "seed", "stability_seeds", "rca_min", "rca_min_group_jobs",
                                       "vec_min_skill_jobs", "gap_min_share_to", "transfer_min_share", "top_gap",
                                       "top_positions", "include_other")}

    print("loading matrix…")
    X, jobs, skills = load_matrix(inp)
    print(f"  {X.shape[0]:,} postings × {X.shape[1]:,} skills, {X.nnz:,} non-zeros")
    print("skill bundles…")
    b = run_bundles(X, jobs, skills, p)
    print(f"  {b['network']}\n  stability {b['stability']}")
    print("occupation transitions…")
    t = run_transitions(X, jobs, skills, p, b.pop("_group"))

    for d in (b["rca"], b["members"], b["coverage"], b["edges"], t["similarity"], t["gaps"], t["transferable"]):
        num = d.select_dtypes("float").columns
        d[num] = d[num].round(6)
    b["rca"].to_csv(out / "rca_by_group.csv", index=False)
    b["communities"].to_csv(out / "communities.csv", index=False)
    b["members"].to_csv(out / "community_members.csv", index=False)
    b["coverage"].to_csv(out / "community_coverage.csv", index=False)
    b["edges"].to_csv(out / "network_edges.csv", index=False)
    t["similarity"].to_csv(out / "group_similarity.csv", index=False)
    t["matrix_share"].to_csv(out / "group_similarity_matrix_share.csv")
    t["matrix_rca"].to_csv(out / "group_similarity_matrix_rca.csv")
    t["gaps"].to_csv(out / "transition_gaps.csv", index=False)
    t["transferable"].to_csv(out / "transition_transferable.csv", index=False)
    if t["positions"] is not None:
        t["positions"].round(6).to_csv(out / "position_similarity.csv", index=False)

    rel = lambda q: str(Path(q).relative_to(ROOT)) if Path(q).is_relative_to(ROOT) else str(q)  # noqa: E731
    partial = len(inp["jobs"]) > 1 or "chunk" in Path(inp["jobs"][0]).name
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    meta = {"generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source": f"{rel(Path(inp['jobs'][0]).parent)} ({len(inp['jobs'])} file(s))", "out_dir": rel(out),
            "n_postings_dedup": int(X.shape[0]), "n_skills": int(X.shape[1]), "params": p,
            "network": b["network"], "stability": b["stability"], "sensitivity": b["sensitivity"], "group_sizes": t["group_sizes"],
            "n_vector_skills": t["n_vector_skills"],
            "group_concentration": t["group_concentration"], "partial_slice": partial,
            "sample_note": ("These tables come from a partial slice of the full run (the first postings in URL order), "
                            "not a random sample: the US is under-weighted and covers only job titles early in the "
                            "alphabet. Treat every figure as provisional until the full run is in."
                            if partial else "Postings are those returned by LinkedIn searches in four English-speaking "
                            "countries in early 2024; they are not a random sample of the labour market."),
            "peak_rss_mb": round(rss / (1024 ** 2 if sys.platform == "darwin" else 1024), 1),
            "quality_note": QUALITY_NOTE}
    (out / "curriculum_meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    write_report(report, meta, b, t)
    print(f"peak RSS {meta['peak_rss_mb']:.0f} MB\ntables → {out}\nreport → {report}")


if __name__ == "__main__":
    main()
