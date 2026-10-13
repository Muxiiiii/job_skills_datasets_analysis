"""Skill-profile clustering and occupation-group prediction from skill sets.

    python -m src.analysis.models                   # pilot: chunks 0-5
    python -m src.analysis.models --preset full     # after the full run

(a) job x skill sparse matrix -> TF-IDF -> NMF topics (k chosen by topic coherence)
    and KMeans clusters (k chosen by cosine silhouette on a sample).
(b) multinomial logistic regression predicting position_group from the skill set,
    stratified train/test split.

Writes tables to <summary-dir>/models/ (read by the Streamlit app) and a markdown report.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.cluster import MiniBatchKMeans
from sklearn.decomposition import NMF
from sklearn.dummy import DummyClassifier
from sklearn.feature_extraction.text import TfidfTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score, silhouette_score
from sklearn.model_selection import train_test_split

from src.analysis.config import QUALITY_NOTE, ROOT, add_input_args, resolve_inputs, sql_list

SEED = 42


def load_matrix(inp: dict, min_skills: int = 3, min_skill_jobs: int = 50, max_jobs: int | None = None):
    """Deduplicated postings x specific skills, binary CSR. Returns (X, jobs_df, skill_names)."""
    con = duckdb.connect()
    con.execute("SET memory_limit='2GB'; SET threads=4")
    long = con.execute(f"""
        WITH jobs AS (
            SELECT job_link, position_group, search_country FROM (
                SELECT *, row_number() OVER (PARTITION BY dup_group_id
                                             ORDER BY is_dup_primary DESC, job_link) AS rn
                FROM read_parquet({sql_list(inp['jobs'])})) WHERE rn = 1)
        SELECT DISTINCT j.job_link, j.position_group, j.search_country, s.skill
        FROM read_parquet({sql_list(inp['skills'])}) s JOIN jobs j USING (job_link)
        WHERE NOT coalesce(s.is_generic, false) AND s.skill NOT LIKE '%(unspecified)%'
    """).df()
    con.close()
    keep_sk = long.skill.value_counts()
    keep_sk = keep_sk[keep_sk >= min_skill_jobs].index
    long = long[long.skill.isin(keep_sk)]
    n_per = long.groupby("job_link").skill.transform("size")
    long = long[n_per >= min_skills]
    jobs = long.drop_duplicates("job_link")[["job_link", "position_group", "search_country"]].reset_index(drop=True)
    if max_jobs and len(jobs) > max_jobs:
        jobs = jobs.sample(max_jobs, random_state=SEED).reset_index(drop=True)
        long = long[long.job_link.isin(set(jobs.job_link))]
    skills = np.array(sorted(long.skill.unique()))
    ji = pd.Series(np.arange(len(jobs)), index=jobs.job_link)
    si = pd.Series(np.arange(len(skills)), index=skills)
    X = sparse.csr_matrix((np.ones(len(long), dtype=np.float32),
                           (ji.loc[long.job_link].to_numpy(), si.loc[long.skill].to_numpy())),
                          shape=(len(jobs), len(skills)))
    return X, jobs, skills


def umass_coherence(top_idx: np.ndarray, Xb: sparse.csr_matrix) -> float:
    """Mean UMass coherence over topics: log((co-doc count + 1) / doc count), higher is better."""
    scores = []
    for idx in top_idx:
        sub = Xb[:, idx]
        co = (sub.T @ sub).toarray()
        df = np.diag(co)
        s = [np.log((co[i, j] + 1) / df[j]) for i in range(1, len(idx)) for j in range(i)]
        scores.append(np.mean(s))
    return float(np.mean(scores))


def top_table(weights: np.ndarray, skills: np.ndarray, n: int, label: str) -> pd.DataFrame:
    rows = []
    for k, w in enumerate(weights):
        for r, i in enumerate(np.argsort(w)[::-1][:n], 1):
            rows.append({label: k, "rank": r, "skill": skills[i], "weight": float(w[i])})
    return pd.DataFrame(rows)


def group_mix(assign: np.ndarray, jobs: pd.DataFrame, label: str) -> pd.DataFrame:
    d = pd.DataFrame({label: assign, "position_group": jobs.position_group.to_numpy()})
    sz = d.groupby(label).size().rename("n_jobs")
    top = (d.groupby([label, "position_group"]).size().rename("n").reset_index()
           .sort_values([label, "n"], ascending=[True, False]))
    top["share"] = top.n / top[label].map(sz)
    top3 = top.groupby(label).head(3).groupby(label).apply(
        lambda g: ", ".join(f"{p.replace('_', ' ')} {s:.0%}" for p, s in zip(g.position_group, g.share)),
        include_groups=False).rename("top_position_groups")
    out = pd.concat([sz, top3], axis=1).reset_index()
    out["share_jobs"] = out.n_jobs / len(d)
    return out


def run_profiles(X, jobs, skills, k_grid, top_n=15, sil_sample=10_000):
    tfidf = TfidfTransformer(sublinear_tf=False).fit_transform(X)
    rng = np.random.default_rng(SEED)
    sel = rng.choice(X.shape[0], size=min(sil_sample, X.shape[0]), replace=False)

    sel_rows, nmf_fits, km_fits = [], {}, {}
    for k in k_grid:
        nmf = NMF(n_components=k, init="nndsvd", random_state=SEED, max_iter=500)
        W = nmf.fit_transform(tfidf)
        top_idx = np.argsort(nmf.components_, axis=1)[:, ::-1][:, :10]
        coh = umass_coherence(top_idx, X)
        # topic diversity: share of unique skills across the top-10 lists
        div = len(np.unique(top_idx)) / top_idx.size
        km = MiniBatchKMeans(n_clusters=k, random_state=SEED, n_init=5, batch_size=4096).fit(tfidf)
        sil = silhouette_score(tfidf[sel], km.labels_[sel], metric="cosine")
        nmf_fits[k], km_fits[k] = (nmf, W), km
        sel_rows.append({"k": k, "nmf_umass_coherence": coh, "nmf_topic_diversity": div,
                         "nmf_recon_err": float(nmf.reconstruction_err_),
                         "kmeans_silhouette_cosine": float(sil), "kmeans_inertia": float(km.inertia_)})
        print(f"  k={k:>2}  NMF coherence={coh:.3f} diversity={div:.2f}   KMeans silhouette={sil:.3f}")
    sel_df = pd.DataFrame(sel_rows)
    k_nmf = int(sel_df.loc[sel_df.nmf_umass_coherence.idxmax(), "k"])
    k_km = int(sel_df.loc[sel_df.kmeans_silhouette_cosine.idxmax(), "k"])

    nmf, W = nmf_fits[k_nmf]
    nmf_top = top_table(nmf.components_, skills, top_n, "topic")
    nmf_sizes = group_mix(W.argmax(axis=1), jobs, "topic")
    km = km_fits[k_km]
    km_top = top_table(km.cluster_centers_, skills, top_n, "cluster")
    km_sizes = group_mix(km.labels_, jobs, "cluster")
    return {"selection": sel_df, "k_nmf": k_nmf, "k_kmeans": k_km, "nmf_top": nmf_top, "nmf_sizes": nmf_sizes,
            "kmeans_top": km_top, "kmeans_sizes": km_sizes}


def run_classifier(X, jobs, skills, include_other=False, test_size=0.2, top_n=10):
    mask = np.ones(len(jobs), bool) if include_other else (jobs.position_group != "Other").to_numpy()
    Xc, y = X[mask], jobs.position_group[mask].to_numpy()
    Xtr, Xte, ytr, yte = train_test_split(Xc, y, test_size=test_size, stratify=y, random_state=SEED)
    tf = TfidfTransformer().fit(Xtr)
    clf = LogisticRegression(max_iter=2000, C=1.0, class_weight="balanced")
    clf.fit(tf.transform(Xtr), ytr)
    pred = clf.predict(tf.transform(Xte))
    base = DummyClassifier(strategy="most_frequent").fit(Xtr, ytr).predict(Xte)
    rep = pd.DataFrame(classification_report(yte, pred, output_dict=True, zero_division=0)).T
    per_class = rep.loc[clf.classes_, ["precision", "recall", "f1-score", "support"]].rename(
        columns={"f1-score": "f1"}).rename_axis("position_group").reset_index()
    per_class["support"] = per_class.support.astype(int)
    top = top_table(clf.coef_, skills, top_n, "class_idx")
    top["position_group"] = top.class_idx.map(dict(enumerate(clf.classes_)))
    top = top.drop(columns="class_idx").rename(columns={"weight": "coef"})[["position_group", "rank", "skill", "coef"]]
    cm = pd.DataFrame(confusion_matrix(yte, pred, labels=clf.classes_), index=clf.classes_, columns=clf.classes_)
    cm_long = cm.rename_axis("true").reset_index().melt("true", var_name="predicted", value_name="n")
    metrics = {"n_train": int(Xtr.shape[0]), "n_test": int(Xte.shape[0]), "n_classes": int(len(clf.classes_)),
               "n_features": int(X.shape[1]), "include_other": include_other,
               "accuracy": float(accuracy_score(yte, pred)),
               "macro_f1": float(f1_score(yte, pred, average="macro")),
               "weighted_f1": float(f1_score(yte, pred, average="weighted")),
               "baseline_majority_accuracy": float(accuracy_score(yte, base)),
               "baseline_majority_macro_f1": float(f1_score(yte, base, average="macro", zero_division=0))}
    return {"metrics": metrics, "per_class": per_class, "top_skills": top, "confusion": cm_long}


def md_table(df: pd.DataFrame, floatfmt="{:.3f}") -> str:
    d = df.copy()
    for c in d.columns:
        if pd.api.types.is_float_dtype(d[c]):
            d[c] = d[c].map(floatfmt.format)
    lines = ["| " + " | ".join(map(str, d.columns)) + " |", "|" + "---|" * len(d.columns)]
    lines += ["| " + " | ".join(map(str, r)) + " |" for r in d.itertuples(index=False)]
    return "\n".join(lines)


def profile_md(top: pd.DataFrame, sizes: pd.DataFrame, label: str) -> str:
    out = []
    for r in sizes.sort_values("n_jobs", ascending=False).itertuples():
        k = getattr(r, label)
        sk = ", ".join(top[top[label] == k].sort_values("rank").skill)
        out.append(f"- **{label} {k}** — {r.n_jobs:,} postings ({r.share_jobs:.1%}); mostly {r.top_position_groups}\n  - {sk}")
    return "\n".join(out)


def boundary_note(prof: dict, grid: list[int]) -> str:
    edge = [n for n, k in (("NMF", prof["k_nmf"]), ("KMeans", prof["k_kmeans"])) if k in (min(grid), max(grid))]
    if not edge:
        return ""
    return (f"**Note:** the selected k for {' and '.join(edge)} sits on the edge of the search grid, i.e. the criterion "
            "is monotone over this range rather than peaking (coherence favours fewer topics, silhouette more clusters; "
            "a wider 4–24 grid on the pilot showed the same trend). The data do not single out a k; "
            "treat these as convenient resolutions, not as the 'true' number of skill profiles.")


def write_report(path: Path, meta: dict, prof: dict, clf: dict):
    m = clf["metrics"]
    top = clf["top_skills"]
    top_md = "\n".join(f"- **{g.replace('_', ' ')}**: " + ", ".join(top[top.position_group == g].sort_values("rank").skill)
                       for g in clf["per_class"].sort_values("support", ascending=False).position_group)
    conf = clf["confusion"]
    conf = conf[conf.true != conf.predicted].sort_values("n", ascending=False).head(8)
    text = f"""# Models report — skill profiles and occupation-group prediction

Input: {meta['n_jobs']:,} deduplicated postings with ≥{meta['min_skills']} specific skills × {meta['n_skills']} skills
(skills appearing in ≥{meta['min_skill_jobs']} postings; generic / unspecified labels excluded). Source: `{meta['source']}`.

> {QUALITY_NOTE}
> Extraction noise (precision≈0.66) blurs both the clusters and the classifier; treat results as descriptive.

## (a) Skill profiles: TF-IDF → NMF / KMeans

Binary posting × skill matrix, TF-IDF weighted (IDF down-weights ubiquitous skills such as Communication).
k was searched over {meta['k_grid']}: NMF by mean UMass topic coherence of each topic's top-10 skills (higher is better),
KMeans by cosine silhouette on a {meta['sil_sample']:,}-posting sample.

{md_table(prof['selection'])}

Selected: **NMF k={prof['k_nmf']}** (best coherence), **KMeans k={prof['k_kmeans']}** (best silhouette).
{boundary_note(prof, meta['k_grid'])}
Silhouette values are low in absolute terms, which is expected for sparse, overlapping skill sets: postings do not
form well-separated clusters, so the profiles are best read as soft themes.

### NMF topics (k={prof['k_nmf']}) — top 15 skills each

Size = postings whose largest topic weight is this topic.

{profile_md(prof['nmf_top'], prof['nmf_sizes'], 'topic')}

### KMeans clusters (k={prof['k_kmeans']}) — top 15 skills by centroid weight

{profile_md(prof['kmeans_top'], prof['kmeans_sizes'], 'cluster')}

## (b) Predicting occupation group from the skill set

Multinomial logistic regression (TF-IDF features, `class_weight="balanced"`, C=1.0) on {m['n_classes']} groups
({'including' if m['include_other'] else 'excluding the catch-all'} `Other`), stratified {m['n_train']:,} train / {m['n_test']:,} test.
The label `position_group` comes from LinkedIn's `search_position`, not from the description, so the target is
independent of the extracted skills.

| metric | logistic regression | majority-class baseline |
|---|---|---|
| accuracy | **{m['accuracy']:.3f}** | {m['baseline_majority_accuracy']:.3f} |
| macro-F1 | **{m['macro_f1']:.3f}** | {m['baseline_majority_macro_f1']:.3f} |
| weighted-F1 | {m['weighted_f1']:.3f} | — |

### Per-class test performance

{md_table(clf['per_class'].sort_values('f1', ascending=False))}

### 10 most important skills per group (largest positive coefficients)

{top_md}

### Most frequent confusions (true → predicted, test set)

{md_table(conf)}

## Caveats

- The pilot slice is not a random sample of the corpus (URL-ordered: AU/CA/UK complete, US only early-alphabet titles); re-run with `--preset full`.
- `position_group` is a coarse mapping of 1,993 search positions; `Management_HR_Admin` in particular is heterogeneous, which caps accuracy.
- Coefficients show association with a group relative to the others, not importance of the skill in absolute demand.
"""
    path.write_text(text)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_input_args(ap)
    ap.add_argument("--k-grid", type=int, nargs="+", default=[6, 8, 10, 12, 14, 16])
    ap.add_argument("--min-skills", type=int, default=3, help="min specific skills per posting")
    ap.add_argument("--min-skill-jobs", type=int, default=50, help="min postings per skill")
    ap.add_argument("--max-jobs", type=int, default=None, help="optional random cap on postings (memory)")
    ap.add_argument("--include-other", action="store_true", help="keep the catch-all Other group as a class")
    ap.add_argument("--report", type=Path, default=ROOT / "outputs" / "models_report.md")
    args = ap.parse_args(argv)
    inp = resolve_inputs(args)
    out = Path(inp["summary_dir"]) / "models"
    out.mkdir(parents=True, exist_ok=True)

    print("loading matrix…")
    X, jobs, skills = load_matrix(inp, args.min_skills, args.min_skill_jobs, args.max_jobs)
    print(f"  {X.shape[0]:,} postings × {X.shape[1]} skills, {X.nnz:,} non-zeros")
    sil_sample = 10_000
    print("skill profiles…")
    prof = run_profiles(X, jobs, skills, args.k_grid, sil_sample=sil_sample)
    print("classifier…")
    clf = run_classifier(X, jobs, skills, include_other=args.include_other)
    print("  ", clf["metrics"])

    prof["selection"].to_csv(out / "k_selection.csv", index=False)
    for name in ("nmf_top", "nmf_sizes", "kmeans_top", "kmeans_sizes"):
        prof[name].to_csv(out / f"{name}.csv", index=False)
    clf["per_class"].to_csv(out / "clf_per_class.csv", index=False)
    clf["top_skills"].to_csv(out / "clf_top_skills.csv", index=False)
    clf["confusion"].to_csv(out / "clf_confusion.csv", index=False)
    src = str(Path(inp["jobs"][0]).parent.relative_to(ROOT)) if Path(inp["jobs"][0]).is_relative_to(ROOT) else str(inp["jobs"][0])
    meta = {"n_jobs": int(X.shape[0]), "n_skills": int(X.shape[1]), "min_skills": args.min_skills,
            "min_skill_jobs": args.min_skill_jobs, "k_grid": args.k_grid, "sil_sample": min(sil_sample, X.shape[0]),
            "k_nmf": prof["k_nmf"], "k_kmeans": prof["k_kmeans"], "source": f"{src} ({len(inp['jobs'])} file(s))",
            "classifier": clf["metrics"]}
    (out / "model_metrics.json").write_text(json.dumps(meta, indent=2))
    write_report(args.report, meta, prof, clf)
    print("report →", args.report)


if __name__ == "__main__":
    main()
