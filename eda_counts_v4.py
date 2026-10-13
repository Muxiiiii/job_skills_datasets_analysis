"""
EDA counting helpers for chain-store JD templates (round4 clarification).

These are NOT cleaning errors: Dollar General / McDonald's post the same title+JD
at thousands of store locations (distinct job_link, distinct location). Rows stay.

Two legitimate skill-demand views:
  - posting  : count every job_link (reflects hiring volume)
  - jd_template: count each (title+company+summary) group once via is_dup_primary
                (reflects distinct skill-requirement templates)

Always report which mode you used.
"""

from __future__ import annotations

from typing import Literal

import pandas as pd

CountMode = Literal["posting", "jd_template"]


def filter_for_count_mode(features: pd.DataFrame, mode: CountMode) -> pd.DataFrame:
    """For jd_template: re-pick one primary per dup_group_id *within this filtered frame*."""
    if mode == "posting":
        return features
    if mode == "jd_template":
        if "dup_group_id" not in features.columns:
            raise KeyError("features need dup_group_id")
        # re-select representative inside current filter (e.g. after country slice)
        feat = features.sort_values("job_link")
        return feat.loc[~feat.duplicated("dup_group_id", keep="first")]
    raise ValueError(f"unknown mode: {mode}")


def skill_counts(
    job_skill: pd.DataFrame,
    features: pd.DataFrame,
    *,
    mode: CountMode = "jd_template",
    skill_col: str = "skill_refined",
    country: str | None = "United States",
    top_n: int = 40,
) -> pd.DataFrame:
    """Top skills under a chosen counting mode (+ optional country filter)."""
    feat = features
    if country is not None and "search_country" in feat.columns:
        feat = feat.loc[feat["search_country"] == country]
    feat = filter_for_count_mode(feat, mode)
    links = set(feat["job_link"])
    js = job_skill.loc[job_skill["job_link"].isin(links)]
    vc = js[skill_col].value_counts().head(top_n).rename("n_jobs").reset_index()
    vc = vc.rename(columns={skill_col: "skill"})
    vc["count_mode"] = mode
    vc["country_filter"] = country or "ALL"
    vc["n_jobs_universe"] = len(feat)
    vc["n_dup_groups"] = (
        feat["dup_group_id"].nunique() if "dup_group_id" in feat.columns else len(feat)
    )
    return vc


def _skill_count_map(
    job_skill: pd.DataFrame,
    features: pd.DataFrame,
    *,
    mode: CountMode,
    skill_col: str,
    country: str | None,
) -> dict[str, int]:
    """Full skill→n_jobs map under a count mode (not truncated to top_n)."""
    feat = features
    if country is not None and "search_country" in feat.columns:
        feat = feat.loc[feat["search_country"] == country]
    feat = filter_for_count_mode(feat, mode)
    links = set(feat["job_link"])
    js = job_skill.loc[job_skill["job_link"].isin(links)]
    return js[skill_col].value_counts().astype(int).to_dict()


def compare_count_modes(
    job_skill: pd.DataFrame,
    features: pd.DataFrame,
    *,
    skill_col: str = "skill_refined",
    country: str | None = "United States",
    top_n: int = 40,
) -> pd.DataFrame:
    """Side-by-side posting vs jd_template top skills for the report.

    Ranking uses posting volume (top_n). Template counts are looked up for those
    same skills from the full template map — never fillna(0) for skills that
    exist but fell outside the template-mode top_n.
    """
    a = skill_counts(job_skill, features, mode="posting", skill_col=skill_col, country=country, top_n=top_n)
    posting_map = _skill_count_map(job_skill, features, mode="posting", skill_col=skill_col, country=country)
    template_map = _skill_count_map(job_skill, features, mode="jd_template", skill_col=skill_col, country=country)
    skills = list(a["skill"])
    rows = []
    for s in skills:
        np_ = int(posting_map.get(s, 0))
        nj = int(template_map.get(s, 0))
        rows.append({
            "skill": s,
            "n_jobs_posting": np_,
            "n_jobs_jd_template": nj,
            "inflation_ratio": (np_ / nj) if nj else None,
            "country_filter": country or "ALL",
        })
    return pd.DataFrame(rows)


def dup_group_summary(features: pd.DataFrame, country: str | None = "United States") -> pd.DataFrame:
    feat = features
    if country is not None and "search_country" in feat.columns:
        feat = feat.loc[feat["search_country"] == country]
    n_postings = len(feat)
    # re-pick primary inside the country filter (do not use global is_dup_primary)
    if "dup_group_id" in feat.columns:
        n_templates = int((~feat.sort_values("job_link").duplicated("dup_group_id", keep="first")).sum())
        n_groups = int(feat["dup_group_id"].nunique())
    else:
        n_templates = n_postings
        n_groups = n_postings
    return pd.DataFrame([{
        "country_filter": country or "ALL",
        "n_postings": n_postings,
        "n_jd_templates": n_templates,
        "n_dup_groups": n_groups,
        "template_share": round(n_templates / n_postings, 4) if n_postings else None,
        "note": (
            "posting=each job_link (hiring volume); "
            "jd_template=one row per title+company+full-summary hash within filter "
            "(skill-demand variety). Chain stores keep all rows — do not delete. "
            "template_family_id is a looser title+company+store-stripped-summary hash."
        ),
    }])
