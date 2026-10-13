"""Stage-6 quality checks for v3 tables."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def check_job_link_unique(df: pd.DataFrame, name: str) -> list[str]:
    errs = []
    if "job_link" not in df.columns:
        return [f"{name}: missing job_link"]
    n_null = df["job_link"].isna().sum()
    if n_null:
        errs.append(f"{name}: {n_null} null job_link")
    if name.startswith("job_features") or name.endswith("_features"):
        n_dup = df["job_link"].duplicated().sum()
        if n_dup:
            errs.append(f"{name}: {n_dup} duplicate job_link")
    return errs


def check_long_unique(js: pd.DataFrame, skill_col: str = "skill_refined") -> list[str]:
    errs = []
    if skill_col not in js.columns:
        skill_col = "skill" if "skill" in js.columns else None
    if not skill_col:
        return ["job_skill: no skill column"]
    dups = js.duplicated(["job_link", skill_col]).sum()
    if dups:
        errs.append(f"job_skill: {dups} duplicate (job_link, {skill_col})")
    return errs


def check_wide_matches_n_skills(wide: pd.DataFrame, features: pd.DataFrame) -> list[str]:
    errs = []
    skill_cols = [c for c in wide.columns if c.startswith("skill_") and c[6:].isdigit()]
    if not skill_cols:
        return ["wide: no skill_N columns"]
    counts = wide[skill_cols].notna().sum(axis=1)
    m = wide[["job_link"]].copy()
    m["wide_n"] = counts.values
    m = m.merge(features[["job_link", "n_skills"]], on="job_link", how="left")
    bad = m[m["wide_n"] != m["n_skills"]]
    # allow jobs where n_skills is 0 and wide empty
    bad = bad[bad["n_skills"].notna()]
    if len(bad):
        errs.append(f"wide vs n_skills mismatch: {len(bad)} jobs (e.g. {bad['job_link'].iloc[0]})")
    return errs


def check_merge_does_not_inflate(before_n: int, after_n: int, label: str) -> list[str]:
    if after_n > before_n:
        return [f"{label}: row count increased after merge ({before_n} → {after_n})"]
    return []


def build_wide_from_long(
    js: pd.DataFrame,
    links: pd.Series,
    skill_col: str = "skill_refined",
    prefer_concrete: bool = True,
) -> pd.DataFrame:
    """skill_1…skill_N; if no concrete skills, fall back to all skills for that job."""
    if skill_col not in js.columns:
        skill_col = "skill"
    rows = []
    by_job = js.groupby("job_link")
    for link in links:
        if link not in by_job.groups:
            rows.append({"job_link": link})
            continue
        g = by_job.get_group(link)
        if prefer_concrete and "is_generic" in g.columns:
            concrete = g.loc[~g["is_generic"].astype(bool), skill_col].dropna().tolist()
            skills = concrete if concrete else g[skill_col].dropna().tolist()
        else:
            skills = g[skill_col].dropna().tolist()
        # dedupe preserving order
        seen, ordered = set(), []
        for s in skills:
            if s not in seen:
                seen.add(s)
                ordered.append(s)
        row = {"job_link": link}
        for i, s in enumerate(ordered, 1):
            row[f"skill_{i}"] = s
        rows.append(row)
    wide = pd.DataFrame(rows)
    # align columns
    skill_cols = sorted(
        [c for c in wide.columns if c.startswith("skill_")],
        key=lambda x: int(x.split("_")[1]),
    )
    return wide[["job_link"] + skill_cols]


def run_all_checks(
    features: pd.DataFrame,
    job_skill: pd.DataFrame,
    wide: pd.DataFrame | None = None,
    evidence: pd.DataFrame | None = None,
) -> pd.DataFrame:
    errs: list[str] = []
    errs += check_job_link_unique(features, "job_features_v3")
    errs += check_long_unique(job_skill)
    if wide is not None and len(wide):
        errs += check_wide_matches_n_skills(wide, features)
        errs += check_job_link_unique(wide, "job_skill_wide_v3")
    if evidence is not None and "job_link" in evidence.columns:
        n_null = evidence["job_link"].isna().sum()
        if n_null:
            errs.append(f"skill_evidence: {n_null} null job_link")

    # note: n_skills tracks wide display count (concrete-first, fallback to all),
    # which may be ≤ unique skills in the long table when generics are hidden.

    if not errs:
        return pd.DataFrame([{"check": "all checks passed", "status": "PASS"}])
    return pd.DataFrame([{"check": e, "status": "FAIL"} for e in errs])
