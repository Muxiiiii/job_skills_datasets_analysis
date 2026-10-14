"""Course priority: a composite ranking of specific skills for curriculum planning.

    python -m src.analysis.course_priority                  # pilot: chunks 0-5
    python -m src.analysis.course_priority --preset full    # full run

Each specific skill (generic and "(unspecified)" labels excluded, at least ``--min-skill-jobs``
postings) is scored on four dimensions, all oriented so that larger = higher priority:

- demand         share of deduplicated postings that mention the skill;
- breadth        number of occupation groups (catch-all Other excluded) where RCA > 1;
- centrality     weighted degree (strength) in the skill co-occurrence network built exactly as in
                 src/analysis/curriculum.py (PMI edge weights, weak edges dropped); PageRank is kept
                 as an alternative column;
- accessibility  optional: entry barrier of the postings that ask for the skill, reverse-scored —
                 median minimum years of experience (postings that state one) and share asking for a
                 bachelor's degree or higher (postings that state a degree), averaged after scaling.

Dimensions are scaled to [0, 1] (min-max by default, or percentile ranks) and combined as a
weighted mean. Weight uncertainty is handled three ways (after OECD & JRC 2008):

A. Monte Carlo: ``--n-draws`` weight vectors from a flat Dirichlet(alpha=1) (uniform on the
   simplex), one ranking per draw → median rank, 5–95 % rank interval, P(top 10), P(top 20).
B. Data-driven weights: entropy weights and CRITIC weights (Diakoulaki et al. 1995).
C. Agreement between the equal-weight, Monte-Carlo-median, entropy and CRITIC rankings
   (Kendall tau, size of the top-10 intersection).

Every step is repeated without accessibility ("3d" variant) as a robustness check, and once per
occupation group with demand and centrality computed inside the group ("by group" table).
Writes CSV/JSON to <summary-dir>/course_priority/ (read by the Streamlit app) and a markdown report.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd
from scipy.stats import kendalltau, rankdata, spearmanr

from src.analysis.config import QUALITY, QUALITY_NOTE, ROOT, add_input_args, resolve_inputs
from src.analysis.curriculum import (MIN_CO_JOBS, MIN_LIFT, MIN_SKILL_JOBS, OTHER_GROUP, RCA_MIN, RCA_MIN_GROUP_JOBS,
                                     build_graph, cooccurrence_edges, group_counts, load_matrix, rca_matrix)

# ---- defaults; every one of these is also a CLI argument --------------------------------
SEED = 42
N_DRAWS = 2000                 # Monte Carlo weight vectors
ALPHA = 1.0                    # Dirichlet concentration (1 = uniform on the simplex)
TOP_K = (10, 20)               # rank thresholds for the "probability of being in the top k" columns
STABLE_P = 0.8                 # P(top 10) at or above this counts as a stable top-10 skill in the report
GROUP_MIN_SKILL_JOBS = RCA_MIN_GROUP_JOBS   # a skill enters a group's ranking with this many postings in the group
BA_PLUS = ("bachelor", "master", "phd", "professional_doctorate")
DIMS_4 = ("demand", "breadth", "centrality", "accessibility")
DIMS_3 = DIMS_4[:3]
VARIANTS = {"4d": DIMS_4, "3d": DIMS_3}
METHODS = ("equal", "mc_median", "entropy", "critic")


# ---------------------------------------------------------------------------------- core maths
def normalize(X: np.ndarray, method: str = "minmax") -> np.ndarray:
    """Column-wise scaling to [0, 1]. Constant columns become 0 (they cannot separate skills)."""
    X = np.asarray(X, dtype=float)
    if method == "percentile":
        return np.column_stack([(rankdata(c, method="average") - 1) / max(len(c) - 1, 1) if np.ptp(c) > 0
                                else np.zeros(len(c)) for c in X.T])
    lo, span = X.min(axis=0), np.ptp(X, axis=0)
    return np.divide(X - lo, span, out=np.zeros_like(X), where=span > 0)


def dirichlet_weights(n_draws: int, k: int, alpha: float = ALPHA, seed: int = SEED) -> np.ndarray:
    """(n_draws, k) weight vectors, each non-negative and summing to 1."""
    return np.random.default_rng(seed).dirichlet(np.full(k, float(alpha)), size=n_draws)


def entropy_weights(Z: np.ndarray) -> np.ndarray:
    """Entropy weight method: dimensions whose values are more evenly spread get less weight.

    p_ij = z_ij / sum_i z_ij,  e_j = -sum_i p_ij ln p_ij / ln n,  w_j ∝ 1 - e_j.
    Z must be non-negative; an all-zero column has no information (weight 0).
    """
    Z = np.asarray(Z, dtype=float)
    n = Z.shape[0]
    tot = Z.sum(axis=0)
    P = np.divide(Z, tot, out=np.zeros_like(Z), where=tot > 0)
    plogp = np.where(P > 0, P * np.log(np.where(P > 0, P, 1.0)), 0.0)
    e = -plogp.sum(axis=0) / np.log(n)
    d = np.where(tot > 0, 1.0 - e, 0.0)
    return d / d.sum() if d.sum() > 0 else np.full(Z.shape[1], 1.0 / Z.shape[1])


def critic_weights(Z: np.ndarray) -> np.ndarray:
    """CRITIC (Diakoulaki et al. 1995): w_j ∝ sigma_j * sum_k (1 - r_jk).

    Contrast (standard deviation) times conflict with the other dimensions (Pearson r), so a
    dimension that varies a lot and is not redundant with the others gets more weight.
    """
    Z = np.asarray(Z, dtype=float)
    sd = Z.std(axis=0, ddof=1)
    ok = sd > 0
    R = np.eye(Z.shape[1])
    if ok.sum() > 1:
        R[np.ix_(ok, ok)] = np.corrcoef(Z[:, ok], rowvar=False)
    c = sd * (1.0 - R).sum(axis=0)
    c[~ok] = 0.0
    return c / c.sum() if c.sum() > 0 else np.full(Z.shape[1], 1.0 / Z.shape[1])


def rank_desc(scores: np.ndarray) -> np.ndarray:
    """Rank 1 = highest score, ties share the best rank; works on (n,) or (n, draws) column-wise."""
    return rankdata(-np.asarray(scores, dtype=float), method="min", axis=0).astype(int)


def rank_distribution(Z: np.ndarray, W: np.ndarray, top_k=TOP_K) -> pd.DataFrame:
    """Rank of every row of Z under every weight vector in W; summary per row."""
    R = rank_desc(np.asarray(Z, dtype=float) @ np.asarray(W, dtype=float).T)   # (n_skills, n_draws)
    d = pd.DataFrame({"mc_median_rank": np.median(R, axis=1), "mc_rank_p05": np.percentile(R, 5, axis=1),
                      "mc_rank_p95": np.percentile(R, 95, axis=1), "mc_mean_rank": R.mean(axis=1)})
    for k in top_k:
        d[f"p_top{k}"] = (R <= k).mean(axis=1)
    return d


def top_set(ranks: np.ndarray, k: int, tiebreak: np.ndarray | None = None) -> set[int]:
    """Indices of the k best ranks (ties broken by ``tiebreak`` ranks, then by index)."""
    tb = np.zeros(len(ranks)) if tiebreak is None else np.asarray(tiebreak, dtype=float)
    return set(np.lexsort((tb, np.asarray(ranks, dtype=float)))[:k].tolist())


def agreement(ranks: dict[str, np.ndarray], k: int = 10) -> pd.DataFrame:
    """Pairwise Kendall tau-b and top-k intersection size between rankings of the same items."""
    rows = []
    ref = ranks.get("equal")
    for a, b in combinations(ranks, 2):
        tau, pval = kendalltau(ranks[a], ranks[b])
        rows.append({"method_a": a, "method_b": b, "kendall_tau": float(tau), "p_value": float(pval),
                     f"top{k}_overlap": len(top_set(ranks[a], k, ref) & top_set(ranks[b], k, ref))})
    return pd.DataFrame(rows)


def score_variant(Z: np.ndarray, p: dict, seed: int) -> tuple[pd.DataFrame, dict, pd.DataFrame]:
    """All rankings of one dimension set. Z: (n_skills, n_dims) scaled dimensions."""
    k = Z.shape[1]
    w = {"equal": np.full(k, 1.0 / k), "entropy": entropy_weights(Z), "critic": critic_weights(Z)}
    out = pd.DataFrame({"score_equal": Z @ w["equal"]})
    out["rank_equal"] = rank_desc(out.score_equal)
    out["rank_entropy"] = rank_desc(Z @ w["entropy"])
    out["rank_critic"] = rank_desc(Z @ w["critic"])
    mc = rank_distribution(Z, dirichlet_weights(p["n_draws"], k, p["alpha"], seed), p["top_k"])
    out = pd.concat([out, mc], axis=1)
    agree = agreement({"equal": out.rank_equal.to_numpy(), "mc_median": out.mc_median_rank.to_numpy(),
                       "entropy": out.rank_entropy.to_numpy(), "critic": out.rank_critic.to_numpy()}, 10)
    return out, w, agree


# ---------------------------------------------------------------------------------- dimensions
def network_centrality(X, n_skill: np.ndarray, names, p: dict) -> pd.DataFrame:
    """Weighted degree and PageRank in the PMI co-occurrence network (curriculum.py thresholds)."""
    Xc = X.tocsc()
    co = np.asarray((Xc.T @ Xc).todense())
    edges = cooccurrence_edges(co, n_skill, X.shape[0], names, p["min_lift"], p["min_co_jobs"], "pmi")
    d = pd.DataFrame({"skill": np.asarray(names)})
    if edges.empty:
        return d.assign(strength=0.0, degree=0, pagerank=0.0)
    G = build_graph(edges)
    pr = nx.pagerank(G, weight="weight")
    d["strength"] = d.skill.map(dict(G.degree(weight="weight"))).fillna(0.0)
    d["degree"] = d.skill.map(dict(G.degree())).fillna(0).astype(int)
    d["pagerank"] = d.skill.map(pr).fillna(0.0)
    return d


def barrier_stats(X, jobs: pd.DataFrame) -> pd.DataFrame:
    """Per skill: median min-YOE among postings stating it, share BA+ among postings stating a degree."""
    yoe = jobs.yoe_min_overall.to_numpy(dtype=float)
    edu = jobs.edu_required.astype(object)
    has_edu = edu.notna().to_numpy()
    ba = edu.isin(BA_PLUS).to_numpy()
    Xc = X.tocsc()
    rows = []
    for s in range(X.shape[1]):
        idx = Xc.indices[Xc.indptr[s]:Xc.indptr[s + 1]]
        y = yoe[idx]
        y = y[~np.isnan(y)]
        e = has_edu[idx]
        rows.append({"yoe_median": float(np.median(y)) if len(y) else np.nan, "n_yoe_stated": int(len(y)),
                     "ba_plus_share": float(ba[idx][e].mean()) if e.any() else np.nan, "n_edu_stated": int(e.sum())})
    return pd.DataFrame(rows)


def accessibility_score(barrier: pd.DataFrame, method: str) -> np.ndarray:
    """Reverse-scored mean of the two scaled barrier measures (missing → column median)."""
    B = barrier[["yoe_median", "ba_plus_share"]].copy()
    B = B.fillna(B.median())
    return 1.0 - normalize(B.to_numpy(), method).mean(axis=1)


def build_dims(X, jobs, skills, p: dict) -> tuple[pd.DataFrame, dict]:
    """Raw and scaled dimensions for every eligible skill (columns of X are eligible skills)."""
    n_total = X.shape[0]
    n_skill = skills.n_jobs.to_numpy()
    counts, n_group, groups = group_counts(X, jobs.position_group)
    rca, _, _ = rca_matrix(counts, n_group, n_total, n_skill)
    keep_g = [i for i, g in enumerate(groups) if g != OTHER_GROUP]
    hit = (rca[keep_g] > p["rca_min"]) & (counts[keep_g] >= p["rca_min_group_jobs"])
    d = skills[["skill", "n_jobs"]].copy()
    d["demand"] = n_skill / n_total
    d["breadth"] = hit.sum(axis=0)
    d["breadth_groups"] = ["; ".join(groups[keep_g[i]] for i in np.flatnonzero(hit[:, s])) for s in range(len(d))]
    cen = network_centrality(X, n_skill, skills.skill.to_numpy(), p)
    d = d.merge(cen, on="skill", how="left")
    d["centrality"] = d.strength
    d = pd.concat([d, barrier_stats(X, jobs)], axis=1)
    d["accessibility"] = accessibility_score(d, p["normalize"])
    Z = normalize(d[list(DIMS_4)].to_numpy(), p["normalize"])
    for j, c in enumerate(DIMS_4):
        d[f"z_{c}"] = Z[:, j]
    info = {"groups": [groups[i] for i in keep_g], "n_groups": len(keep_g),
            "spearman_strength_pagerank": float(spearmanr(d.strength, d.pagerank)[0])}
    return d, info


def build_group_dims(X, jobs, skills, dims: pd.DataFrame, p: dict) -> pd.DataFrame:
    """Per occupation group: demand and centrality inside the group; breadth and accessibility global."""
    parts = []
    codes = jobs.position_group.astype("category")
    for g in codes.cat.categories:
        if g == OTHER_GROUP:
            continue
        rows = np.flatnonzero((codes == g).to_numpy())
        Xg = X[rows]
        n_g = np.asarray(Xg.sum(axis=0)).ravel()
        keep = np.flatnonzero(n_g >= p["group_min_skill_jobs"])
        if len(keep) < 2:
            continue
        Xg = Xg[:, keep]
        cen = network_centrality(Xg, n_g[keep], skills.skill.to_numpy()[keep], p)
        d = pd.DataFrame({"position_group": g, "skill": skills.skill.to_numpy()[keep], "n_jobs_in_group": len(rows),
                          "n_jobs": n_g[keep].astype(int), "demand": n_g[keep] / len(rows),
                          "centrality": cen.strength.to_numpy(), "degree": cen.degree.to_numpy()})
        d = d.merge(dims[["skill", "breadth", "accessibility"]], on="skill", how="left")
        Z = normalize(d[list(DIMS_4)].to_numpy(), p["normalize"])
        for j, c in enumerate(DIMS_4):
            d[f"z_{c}"] = Z[:, j]
        parts.append(d)
    return pd.concat(parts, ignore_index=True)


def rank_all(d: pd.DataFrame, p: dict, seed: int, keys: list[str]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Score every variant of one dimension table. Returns (ranking, weights, agreement) long tables.

    Also adds the equal-weight rank under the other scaling (min-max <-> percentile) as a sensitivity column.
    """
    rk, wt, ag = [], [], []
    alt = "percentile" if p["normalize"] == "minmax" else "minmax"
    for v, cols in VARIANTS.items():
        out, w, agree = score_variant(d[[f"z_{c}" for c in cols]].to_numpy(), p, seed)
        out[f"rank_equal_{alt}"] = rank_desc(normalize(d[list(cols)].to_numpy(), alt).mean(axis=1))
        rk.append(pd.concat([d[keys].reset_index(drop=True), out], axis=1).assign(variant=v))
        wt += [{"variant": v, "method": m, "dim": c, "weight": float(w[m][j])} for m in w for j, c in enumerate(cols)]
        ag.append(agree.assign(variant=v))
    return pd.concat(rk, ignore_index=True), pd.DataFrame(wt), pd.concat(ag, ignore_index=True)


# ---------------------------------------------------------------------------------- report
REFERENCES = [
    "OECD & JRC (2008). *Handbook on Constructing Composite Indicators: Methodology and User Guide*. OECD Publishing, Paris.",
    "Saisana, M., Saltelli, A. & Tarantola, S. (2005). Uncertainty and sensitivity analysis techniques as tools for the "
    "quality assessment of composite indicators. *Journal of the Royal Statistical Society: Series A*, 168(2), 307–323.",
    "Diakoulaki, D., Mavrotas, G. & Papayannakis, L. (1995). Determining objective weights in multiple criteria problems: "
    "the CRITIC method. *Computers & Operations Research*, 22(7), 763–770.",
    "Alabdulkareem, A., Frank, M. R., Sun, L., AlShebli, B., Hidalgo, C. & Rahwan, I. (2018). Unpacking the polarization "
    "of workplace skills. *Science Advances*, 4(7), eaao6030.",
    "Dawson, N., Williams, M.-A. & Rizoiu, M.-A. (2021). Skill-driven recommendations for job transition pathways. "
    "*PLoS ONE*, 16(8), e0254722.",
]


def _rank_line(r) -> str:
    return (f"| {int(r.rank_equal)} | {r.skill} | {r.score_equal:.3f} | {r.mc_median_rank:.0f} | "
            f"{r.mc_rank_p05:.0f}–{r.mc_rank_p95:.0f} | {r.p_top10:.2f} | {r.p_top20:.2f} | "
            f"{int(r.rank_entropy)} | {int(r.rank_critic)} |")


def write_report(path: Path, meta: dict, dims: pd.DataFrame, rk: pd.DataFrame, wt: pd.DataFrame,
                 ag: pd.DataFrame, grp: pd.DataFrame | None) -> None:
    p = meta["params"]
    r4 = rk[rk.variant == "4d"].sort_values("rank_equal")
    r3 = rk[rk.variant == "3d"].sort_values("rank_equal")
    stable = r4[r4.p_top10 >= p["stable_p"]].sort_values("p_top10", ascending=False)
    stable20 = r4[r4.p_top20 >= p["stable_p"]].sort_values("p_top20", ascending=False)
    alt = "percentile" if p["normalize"] == "minmax" else "minmax"
    t_alt = kendalltau(r4.rank_equal, r4[f"rank_equal_{alt}"])[0]
    ov_alt = len(top_set(r4.rank_equal.to_numpy(), 10) & top_set(r4[f"rank_equal_{alt}"].to_numpy(), 10, r4.rank_equal.to_numpy()))
    W = wt.pivot_table(index=["variant", "method"], columns="dim", values="weight")
    corr = dims[list(DIMS_4)].corr(method="spearman")
    L = ["# Course priority: a composite ranking of skills for curriculum planning", "",
         f"Source: `{meta['source']}` — {meta['n_postings_dedup']:,} deduplicated postings, "
         f"{meta['n_skills']} specific skills with ≥ {p['min_skill_jobs']} postings. Generated {meta['generated_at_utc']}.", "",
         "Reproduce with `python -m src.analysis.course_priority` (pilot) or `--preset full`. "
         f"Tables are in `{meta['out_dir']}/`.", "",
         "## Method", "",
         "**Unit and filters.** One posting per `dup_group_id`; generic and `(unspecified)` labels excluded; a skill "
         f"needs ≥ {p['min_skill_jobs']} postings (same eligibility as the co-occurrence network in the curriculum analysis).", "",
         "**Dimensions** (all oriented so that larger = higher priority):", "",
         "| Dimension | Definition | Why it matters for a course |", "|---|---|---|",
         "| Demand | Share of deduplicated postings that mention the skill. | How many jobs the course serves. |",
         f"| Breadth | Number of the {meta['n_groups']} occupation groups (`{OTHER_GROUP}` excluded) where the skill's RCA "
         f"> {p['rca_min']:g} with ≥ {p['rca_min_group_jobs']} postings in the group. | Transferability across fields. |",
         f"| Centrality | Weighted degree (sum of PMI edge weights) in the co-occurrence network: edge if lift > "
         f"{p['min_lift']:g} and ≥ {p['min_co_jobs']} co-occurring postings. PageRank is kept as an alternative "
         f"(Spearman with weighted degree {meta['spearman_strength_pagerank']:.2f}). | Skills that connect to many others "
         "anchor a bundle (Alabdulkareem et al. 2018). PMI is prevalence-adjusted, so very common skills score low "
         "here by construction (a skill in a share *s* of postings has lift ≤ 1/*s*); prevalence is carried by demand. |",
         "| Accessibility (optional) | Reverse-scored mean of (a) median minimum years of experience among postings with "
         "the skill that state YOE and (b) share asking for a bachelor's degree or higher among postings with the skill "
         "that state a degree. | Entry-level reach; it is a learner-side judgement, so it is reported with and without. |", "",
         f"**Scaling.** {'Min-max to [0, 1]' if p['normalize'] == 'minmax' else 'Percentile ranks in [0, 1]'} per "
         "dimension; composite = weighted mean of the scaled dimensions.", "",
         "**Weights** (OECD & JRC 2008, ch. 6–7; Saisana, Saltelli & Tarantola 2005):", "",
         f"- *Equal weights* — the headline ranking.",
         f"- *Method A, Monte Carlo* — {p['n_draws']:,} weight vectors from a flat Dirichlet(α = {p['alpha']:g}) "
         f"(uniform over all weightings that sum to 1; seed {p['seed']}). Each draw gives a ranking; we report the median "
         "rank, the 5–95 % rank interval and the probability of landing in the top 10 / top 20.",
         "- *Method B, data-driven* — entropy weights (more weight to dimensions that separate skills more sharply) and "
         "CRITIC weights (Diakoulaki et al. 1995: standard deviation × conflict with the other dimensions).",
         "- *Agreement* — Kendall tau-b and top-10 intersection between the equal-weight, Monte Carlo median, entropy "
         "and CRITIC rankings.",
         "- *Robustness* — everything is repeated without accessibility (\"3d\").", "",
         "Weights used:", "",
         "| Variant | Method | " + " | ".join(DIMS_4) + " |", "|---|---|" + "---|" * len(DIMS_4)]
    for (v, m), row in W.iterrows():
        L.append(f"| {v} | {m} | " + " | ".join("–" if pd.isna(row.get(c)) else f"{row[c]:.3f}" for c in DIMS_4) + " |")
    L += ["", "Spearman correlation between the raw dimensions (high values mean two dimensions largely double-count):", "",
          "| | " + " | ".join(DIMS_4) + " |", "|---|" + "---|" * len(DIMS_4)]
    L += [f"| {a} | " + " | ".join(f"{corr.at[a, b]:.2f}" for b in DIMS_4) + " |" for a in DIMS_4]
    L += ["", "## Results (four dimensions)", "",
          "| Equal-weight rank | Skill | Score | MC median rank | MC 5–95 % | P(top 10) | P(top 20) | Entropy rank | CRITIC rank |",
          "|---|---|---|---|---|---|---|---|---|"]
    L += [_rank_line(r) for r in r4.head(25).itertuples()]
    L += ["", f"**Stable top-10 skills** (P(top 10) ≥ {p['stable_p']:.1f} under random weights): "
          + (", ".join(f"{r.skill} ({r.p_top10:.2f})" for r in stable.itertuples()) or "none") + ".", "",
          f"**Stable top-20 skills** (P(top 20) ≥ {p['stable_p']:.1f}): "
          + (", ".join(f"{r.skill} ({r.p_top20:.2f})" for r in stable20.itertuples()) or "none") + ".", "",
          f"**Scaling sensitivity.** With {alt} scaling instead of {p['normalize']}, the equal-weight ranking has Kendall "
          f"tau {t_alt:.3f} with the one above and shares {ov_alt}/10 of its top 10.", ""]
    for v, d in ag.groupby("variant", sort=False):
        L += [f"**Agreement between methods ({v}):**", "", "| Method A | Method B | Kendall tau | Top-10 overlap |",
              "|---|---|---|---|"]
        L += [f"| {r.method_a} | {r.method_b} | {r.kendall_tau:.3f} | {r.top10_overlap}/10 |" for r in d.itertuples()]
        L.append("")
    t43 = kendalltau(r4.set_index("skill").rank_equal, r3.set_index("skill").rank_equal.reindex(r4.skill))[0]
    ov = len(set(r4.head(10).skill) & set(r3.head(10).skill))
    L += ["## Robustness: without accessibility (three dimensions)", "",
          f"Kendall tau between the 4d and 3d equal-weight rankings: {t43:.3f}; top-10 overlap {ov}/10.", "",
          "| Equal-weight rank | Skill | Score | MC median rank | MC 5–95 % | P(top 10) | P(top 20) | Entropy rank | CRITIC rank |",
          "|---|---|---|---|---|---|---|---|---|"]
    L += [_rank_line(r) for r in r3.head(15).itertuples()]
    if grp is not None and len(grp):
        g4 = grp[grp.variant == "4d"]
        L += ["", "## By occupation group (four dimensions, equal weights)", "",
              "Demand and centrality are recomputed inside each group (network over the group's postings, same "
              f"thresholds; skills with ≥ {p['group_min_skill_jobs']} postings in the group); breadth and accessibility "
              "are the corpus-wide values.", "", "| Occupation group | Postings | Top 8 (P(top 10) under random weights) |",
              "|---|---|---|"]
        for g, d in g4.groupby("position_group"):
            d = d.sort_values("rank_equal")
            L.append(f"| {g.replace('_', ' ')} | {int(d.n_jobs_in_group.iat[0]):,} | "
                     + ", ".join(f"{r.skill} ({r.p_top10:.2f})" for r in d.head(8).itertuples()) + " |")
    L += ["", "## Limitations", "",
          "- **No growth dimension.** The postings are a single snapshot (early 2024), so the ranking says nothing about "
          "rising or declining demand; a trend dimension needs a second period.",
          f"- **Extraction noise.** Skill precision ≈ {QUALITY['skill_precision']:.2f}, recall ≈ {QUALITY['skill_recall']:.2f} "
          "on 50 unseen postings. Demand and co-occurrence inherit this error; small score differences are not meaningful, "
          "so read the rank intervals rather than the point ranks.",
          "- **Choice of weight range.** The flat Dirichlet treats every weighting as equally plausible, including extreme "
          "ones (e.g. almost all weight on one dimension). Narrower priors (larger α) would give tighter intervals; the "
          "intervals here are therefore deliberately conservative. Entropy and CRITIC weights are properties of this "
          "data's spread, not statements about what matters for teaching.",
          "- **Skewed demand.** A handful of skills appear in a large share of postings and most in under 3 %; min-max "
          "scaling compresses the long tail of demand, which is why entropy weighting puts most weight on demand. The "
          "scaling-sensitivity line above shows how much this matters.",
          "- **Dimension overlap.** Check the correlation table above before reading equal weights as balanced: any "
          "strongly correlated pair double-counts the same signal.",
          "- **Accessibility is a proxy.** YOE and degree requirements are stated in a minority of postings (accuracy when "
          "stated ≈ 0.84 / 0.86); the dimension describes the jobs, not how hard the skill is to learn.",
          "- **Breadth uses RCA > 1**, so a skill requested everywhere at similar rates (e.g. Communication) can have low "
          "breadth: breadth rewards being *over-represented* in many groups, not merely present.",
          f"- **Sample.** {meta['sample_note']}", "",
          "## References", ""]
    L += [f"- {r}" for r in REFERENCES]
    L.append("")
    path.write_text("\n".join(L))


# ---------------------------------------------------------------------------------- CLI
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_input_args(ap)
    ap.add_argument("--min-skill-jobs", type=int, default=MIN_SKILL_JOBS, help="min postings for an eligible skill")
    ap.add_argument("--min-lift", type=float, default=MIN_LIFT)
    ap.add_argument("--min-co-jobs", type=int, default=MIN_CO_JOBS)
    ap.add_argument("--rca-min", type=float, default=RCA_MIN)
    ap.add_argument("--rca-min-group-jobs", type=int, default=RCA_MIN_GROUP_JOBS)
    ap.add_argument("--group-min-skill-jobs", type=int, default=GROUP_MIN_SKILL_JOBS)
    ap.add_argument("--normalize", choices=["minmax", "percentile"], default="minmax")
    ap.add_argument("--n-draws", type=int, default=N_DRAWS)
    ap.add_argument("--alpha", type=float, default=ALPHA, help="Dirichlet concentration")
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--stable-p", type=float, default=STABLE_P)
    ap.add_argument("--no-groups", action="store_true", help="skip the per-occupation-group rankings")
    ap.add_argument("--report", type=Path, help="default: outputs/course_priority_report.md (pilot) / _full.md (full)")
    args = ap.parse_args(argv)
    inp = resolve_inputs(args)
    out = Path(inp["summary_dir"]) / "course_priority"
    out.mkdir(parents=True, exist_ok=True)
    report = args.report or ROOT / "outputs" / ("course_priority_report.md" if args.preset == "pilot"
                                                else f"course_priority_report_{args.preset}.md")
    p = {k: getattr(args, k) for k in ("min_skill_jobs", "min_lift", "min_co_jobs", "rca_min", "rca_min_group_jobs",
                                       "group_min_skill_jobs", "normalize", "n_draws", "alpha", "seed", "stable_p")}
    p["top_k"] = list(TOP_K)

    print("loading matrix…")
    X, jobs, skills = load_matrix(inp, extra_cols=("yoe_min_overall", "edu_required"))
    n_total = X.shape[0]
    elig = np.flatnonzero(skills.n_jobs.to_numpy() >= p["min_skill_jobs"])
    X, skills = X[:, elig].tocsr(), skills.iloc[elig].reset_index(drop=True)
    print(f"  {n_total:,} postings × {X.shape[1]} eligible skills")

    print("dimensions…")
    dims, info = build_dims(X, jobs, skills, p)
    meta_sk = pd.read_csv(Path(inp["summary_dir"]) / "skill_meta.csv") if (Path(inp["summary_dir"]) / "skill_meta.csv").exists() else None
    if meta_sk is not None:
        dims = dims.merge(meta_sk, on="skill", how="left")
    print("rankings…")
    rk, wt, ag = rank_all(dims, p, p["seed"], ["skill"])
    grp = gwt = gag = None
    if not args.no_groups:
        print("rankings by occupation group…")
        gd = build_group_dims(X, jobs, skills, dims, p)
        parts = {g: rank_all(d.reset_index(drop=True), p, p["seed"],
                             ["position_group", "skill", "n_jobs_in_group", "n_jobs", "demand", "centrality"])
                 for g, d in gd.groupby("position_group")}
        grp = pd.concat([x[0] for x in parts.values()], ignore_index=True)
        gwt = pd.concat([x[1].assign(position_group=g) for g, x in parts.items()], ignore_index=True)
        gag = pd.concat([x[2].assign(position_group=g) for g, x in parts.items()], ignore_index=True)
        gz = gd[["position_group", "skill"] + [f"z_{c}" for c in DIMS_4]]
        grp = grp.merge(gz, on=["position_group", "skill"], how="left")

    rk = rk.merge(dims[["skill"] + [f"z_{c}" for c in DIMS_4]], on="skill", how="left")
    for d in (dims, rk, wt, ag, grp, gwt, gag):
        if d is not None:
            num = d.select_dtypes("float").columns
            d[num] = d[num].round(6)
    dims.sort_values("demand", ascending=False).to_csv(out / "dimensions.csv", index=False)
    rk.sort_values(["variant", "rank_equal"]).to_csv(out / "ranking.csv", index=False)
    wt.to_csv(out / "weights.csv", index=False)
    ag.to_csv(out / "agreement.csv", index=False)
    if grp is not None:
        grp.sort_values(["variant", "position_group", "rank_equal"]).to_csv(out / "ranking_by_group.csv", index=False)
        gwt.to_csv(out / "weights_by_group.csv", index=False)
        gag.to_csv(out / "agreement_by_group.csv", index=False)

    rel = lambda q: str(Path(q).relative_to(ROOT)) if Path(q).is_relative_to(ROOT) else str(q)  # noqa: E731
    partial = len(inp["jobs"]) > 1 or "chunk" in Path(inp["jobs"][0]).name
    r4 = rk[rk.variant == "4d"]
    meta = {"generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source": f"{rel(Path(inp['jobs'][0]).parent)} ({len(inp['jobs'])} file(s))", "out_dir": rel(out),
            "n_postings_dedup": int(n_total), "n_skills": int(X.shape[1]), "params": p, **info,
            "dims": {"4d": list(DIMS_4), "3d": list(DIMS_3)},
            "top10_equal_4d": r4.sort_values("rank_equal").skill.head(10).tolist(),
            "stable_top10_4d": r4[r4.p_top10 >= p["stable_p"]].sort_values("p_top10", ascending=False).skill.tolist(),
            "stable_top20_4d": r4[r4.p_top20 >= p["stable_p"]].sort_values("p_top20", ascending=False).skill.tolist(),
            "partial_slice": partial,
            "sample_note": ("These tables come from a partial slice of the full run (the first 300k postings in URL "
                            "order), not a random sample: the US is under-weighted and covers only job titles early in "
                            "the alphabet. Use the full-run tables for decisions."
                            if partial else "Postings are those returned by LinkedIn searches in four English-speaking "
                            "countries in early 2024; they are not a random sample of the labour market."),
            "quality_note": QUALITY_NOTE}
    (out / "course_priority_meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    write_report(report, meta, dims, rk, wt, ag, grp)
    print("top 10 (equal weights):", meta["top10_equal_4d"])
    print("stable top 10:", meta["stable_top10_4d"], "\nstable top 20:", meta["stable_top20_4d"])
    print(ag.to_string(index=False))
    print(f"tables → {out}\nreport → {report}")


if __name__ == "__main__":
    main()
