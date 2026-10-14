"""
v8 pipeline — fixed sample, round8 precision/recall/family/quals fixes.

Reads cleaned/sample_links_v5.csv (never re-samples). Outputs *_v8_*.
Holdout is not evaluated — rules freeze after this round.
"""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

import config_v4 as cfg
from extraction_resources import (
    AMBIGUOUS_FOR_SUMMARY,
    COURSE_DOMAIN,
    KEEP_RE,
    NOT_A_SKILL_RE,
    SKILL_DICT,
    SKILL_TYPE,
    aggregate_yoe,
    context_filter_skill,
    extract_cert_records,
    extract_education_records,
    extract_yoe_records,
    requirement_text,
    skills_extraction_status,
    summarize_education,
)
from skill_refinement import (
    assign_job_family_detailed,
    build_alias_to_skill,
    build_summary_keyword_processor,
    extract_skill_evidence,
    load_alias_tables,
    refine_skill_table,
    split_sections_typed,
)
from quality_checks_v3 import build_wide_from_long
from eda_counts_v4 import compare_count_modes, dup_group_summary

OUT = cfg.CLEANED
TAG = cfg.TAG
SUF = "v8"
SAMPLE_LINKS = OUT / "sample_links_v5.csv"


def is_noise_token(tok: str) -> bool:
    if KEEP_RE.search(tok):
        return False
    return bool(NOT_A_SKILL_RE.search(tok))


def load_fixed_base() -> pd.DataFrame:
    assert SAMPLE_LINKS.exists(), f"Missing {SAMPLE_LINKS}"
    links = pd.read_csv(SAMPLE_LINKS)
    links = links.sort_values("job_link").drop_duplicates()
    con = duckdb.connect()
    con.register("sample_links", links)
    base = con.execute(
        """
        SELECT c.*
        FROM sample_links sl
        JOIN read_parquet(?) c ON sl.job_link = c.job_link
        ORDER BY sl.job_link
        """,
        [str(cfg.JOBS_COMBINED)],
    ).df()
    con.close()
    if len(base) != len(links):
        raise SystemExit(f"sample join mismatch: links={len(links)} joined={len(base)}")
    return base


def normalize_summary(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").lower()).strip()


def strip_store_noise(s: str) -> str:
    t = normalize_summary(s)
    t = re.sub(r"\b\d{3,6}\b", " ", t)  # store #s
    t = re.sub(r"\b[a-z]{2}\s+\d{5}(?:-\d{4})?\b", " ", t)  # state zip
    return re.sub(r"\s+", " ", t).strip()


def assign_dup_ids(df: pd.DataFrame) -> pd.DataFrame:
    """Full-summary hash; empty summary → singleton group. Plus loose template_family_id."""
    df = df.copy()
    groups, families, primary = [], [], []
    seen_primary = {}
    for r in df.itertuples(index=False):
        title = str(r.job_title or "")
        company = str(r.company or "")
        summ = r.job_summary if isinstance(r.job_summary, str) else ""
        if not summ.strip():
            gid = "singleton:" + hashlib.md5(str(r.job_link).encode()).hexdigest()[:12]
        else:
            gid = hashlib.md5(f"{title.lower()}|{company.lower()}|{normalize_summary(summ)}".encode()).hexdigest()[:16]
        fam = hashlib.md5(
            f"{title.lower()}|{company.lower()}|{strip_store_noise(summ)}".encode()
        ).hexdigest()[:16]
        groups.append(gid)
        families.append(fam)
        if gid not in seen_primary:
            seen_primary[gid] = r.job_link
        primary.append(r.job_link == seen_primary[gid])
    df["dup_group_id"] = groups
    df["template_family_id"] = families
    df["is_dup_primary"] = primary
    return df


def text_status_row(r) -> str:
    skills = r.job_skills if isinstance(r.job_skills, str) else ""
    summary = r.job_summary if isinstance(r.job_summary, str) else ""
    if skills.strip() or summary.strip():
        return "ok"
    if bool(getattr(r, "skills_is_missing", True)) and bool(getattr(r, "summary_is_missing", True)):
        return "missing_in_raw"
    return "missing_in_cache"


def extract_quals(summary: str, title: str) -> dict:
    sections = split_sections_typed(summary) if summary else []
    yoe_rows, edu_rows, cert_rows = [], [], []
    has_req = any(s["section_type"] in {"requirements", "preferred"} for s in sections)
    # Inline "Requirements:" / "Education … Requirements" even inside an untyped blob
    inline_req = bool(re.search(
        r"(?i)\b(?:minimum\s+)?(?:qualifications|requirements)\b|"
        r"\beducation\s+and\s+experience\s+requirements?\b",
        summary or "",
    ))
    if sections:
        for s in sections:
            st = s["section_type"]
            # Skip company/eeo for skills-like quals; still allow YOE/edu from benefits? No —
            # but licenses often sit under a mis-tagged Benefits header.
            if st in {"company", "eeo"}:
                continue
            if st == "benefits":
                # only pull license/cert mentions out of benefits blobs
                for cr in extract_cert_records(s["text"], title=None):
                    cr = dict(cr)
                    cr["section_type"] = "benefits"
                    cert_rows.append(cr)
                continue
            yoe_rows.extend(extract_yoe_records(s["text"], section_type=st))
            edu_rows.extend(extract_education_records(
                s["text"],
                has_req_section=(st in {"requirements", "preferred"} or inline_req),
                section_type=("requirements" if (st == "other" and inline_req) else st),
            ))
            for cr in extract_cert_records(s["text"], title=None):
                cr = dict(cr)
                cr["section_type"] = st
                if st == "preferred":
                    cr["cert_status"] = "preferred" if cr.get("cert_status") != "title_mention" else cr["cert_status"]
                cert_rows.append(cr)
    else:
        req, has_req = requirement_text(summary or "")
        yoe_rows = extract_yoe_records(req)
        edu_rows = extract_education_records(req, has_req_section=has_req or inline_req)
        cert_rows = extract_cert_records(req, title=title)
        for cr in cert_rows:
            cr["section_type"] = "requirements" if has_req else "other"

    # Always scan full JD for licenses (curly-apostrophe / odd sections)
    seen_cert = {(c.get("certification"), c.get("matched_text")) for c in cert_rows}
    for cr in extract_cert_records(summary or "", title=None):
        key = (cr.get("certification"), cr.get("matched_text"))
        if key in seen_cert:
            continue
        cr = dict(cr)
        cr["section_type"] = cr.get("section_type") or "full_scan"
        cert_rows.append(cr)

    # title-only certs
    for cr in extract_cert_records("", title=title):
        cr = dict(cr)
        cr["section_type"] = "title"
        cert_rows.append(cr)

    edu_sum = summarize_education(edu_rows)
    edu_sum["edu_or_equiv"] = bool(re.search(r"(?i)or equivalent (?:work )?experience", summary or ""))
    yoe_agg = aggregate_yoe(yoe_rows)
    body_certs = [
        c["certification"] for c in cert_rows
        if c.get("source_field") != "title" and c.get("cert_status") in {"required", "mentioned", "preferred"}
    ]
    return {
        "has_req_section": has_req,
        "edu": edu_sum, "edu_rows": edu_rows,
        "yoe": yoe_agg, "yoe_rows": yoe_rows,
        "cert_rows": cert_rows,
        "certs": list(dict.fromkeys(body_certs)),
    }


def split_validation(features: pd.DataFrame, seed: int = 42):
    """200 jobs; same dup_group_id cannot appear in both tune and holdout."""
    rng = np.random.default_rng(seed)
    feat = features.sort_values("job_link").reset_index(drop=True)
    # sample groups proportional to family
    fam_counts = feat["job_family"].fillna("Other").value_counts()
    target_n = 200
    alloc = (fam_counts / fam_counts.sum() * target_n).apply(np.floor).astype(int)
    while alloc.sum() < target_n:
        frac = fam_counts / fam_counts.sum() * target_n - alloc
        alloc.loc[frac.idxmax()] += 1
    while alloc.sum() > target_n:
        alloc.loc[alloc.idxmax()] -= 1

    picked_idx = []
    used_groups = set()
    for fam, k in alloc.items():
        pool = feat.loc[feat["job_family"].fillna("Other") == fam]
        # pick unique dup groups
        order = rng.permutation(pool.index.to_numpy())
        got = 0
        for i in order:
            g = pool.loc[i, "dup_group_id"]
            if g in used_groups:
                continue
            picked_idx.append(i)
            used_groups.add(g)
            got += 1
            if got >= k:
                break
    sample = feat.loc[picked_idx].copy()
    if len(sample) < target_n:
        rest = feat.loc[~feat.index.isin(picked_idx)]
        for i in rng.permutation(rest.index.to_numpy()):
            g = rest.loc[i, "dup_group_id"]
            if g in used_groups:
                continue
            sample = pd.concat([sample, rest.loc[[i]]])
            used_groups.add(g)
            if len(sample) >= target_n:
                break
    sample = sample.head(target_n).copy()

    # holdout 50 groups
    groups = sample["dup_group_id"].unique()
    hold_g = set(rng.choice(groups, size=min(50, len(groups)), replace=False))
    sample["split"] = sample["dup_group_id"].map(lambda g: "holdout" if g in hold_g else "tune")
    # fix counts to ~150/50 by moving whole groups
    while (sample["split"] == "holdout").sum() > 50:
        g = sample.loc[sample["split"] == "holdout", "dup_group_id"].iloc[0]
        sample.loc[sample["dup_group_id"] == g, "split"] = "tune"
    while (sample["split"] == "holdout").sum() < 50:
        g = sample.loc[sample["split"] == "tune", "dup_group_id"].iloc[0]
        sample.loc[sample["dup_group_id"] == g, "split"] = "holdout"

    tune = sample[sample["split"] == "tune"]
    full_idx = list(rng.choice(tune.index.to_numpy(), size=min(30, len(tune)), replace=False))
    sample["full_recall"] = sample.index.isin(full_idx)
    return sample


def classify_boilerplate(skill: str, evidence: pd.DataFrame, features: pd.DataFrame) -> str:
    sub = evidence.loc[
        (evidence["skill"] == skill) & evidence["evidence"].notna(),
        ["job_link", "evidence"],
    ]
    if len(sub) < 20:
        return "独立JD的常见表达"
    top = sub["evidence"].astype(str).value_counts()
    top_ev, top_n = top.index[0], int(top.iloc[0])
    share = top_n / len(sub)
    if share < 0.20:
        return "独立JD的常见表达"
    links = sub.loc[sub["evidence"].astype(str) == top_ev, "job_link"]
    meta = features.loc[features["job_link"].isin(links), ["company", "dup_group_id", "job_location"]]
    n_loc = meta["job_location"].nunique() if "job_location" in meta.columns else 0
    n_co = meta["company"].nunique()
    n_g = meta["dup_group_id"].nunique()
    ev_l = top_ev.lower()
    if any(w in ev_l for w in ("referral", "401", "dental", "vision", "insurance", "pto", "benefit")):
        return "福利或套话误命中"
    if n_g <= 3 and n_loc >= 5:
        return "同模板多地点"
    if n_co == 1 and n_loc >= 3:
        return "同模板多地点"
    return "独立JD的常见表达"


def main():
    print("=== v8 pipeline (fixed sample) ===")
    base = load_fixed_base()
    base = assign_dup_ids(base)
    print(f"jobs={len(base)} countries=\n{base['search_country'].value_counts().head()}")

    # family — load frozen classifier only (never retrain / overwrite joblib)
    from job_family_classifier import predict_job_family, load_model, MODEL_PATH
    if not MODEL_PATH.exists():
        raise SystemExit(f"Frozen job_family model missing: {MODEL_PATH}")
    load_model()  # load-only; raises if missing after guard above
    fam_rows = []
    for title, link, summ in zip(base["job_title"], base["job_link"], base["job_summary"]):
        d = predict_job_family(
            title if isinstance(title, str) else "",
            summ if isinstance(summ, str) else "",
        )
        d["job_link"] = link
        d["job_title"] = title
        fam_rows.append(d)
    family_df = pd.DataFrame(fam_rows)
    family_by_link = dict(zip(family_df["job_link"], family_df["job_family"]))
    title_by_link = dict(zip(base["job_link"], base["job_title"]))

    alias_to = build_alias_to_skill(SKILL_DICT)
    summary_kp = build_summary_keyword_processor(SKILL_DICT, AMBIGUOUS_FOR_SUMMARY)

    evidence_rows, token_logs, filtered_hits = [], [], []
    eid = 1
    for r in base.itertuples(index=False):
        evs, logs = extract_skill_evidence(
            r.job_skills, r.job_summary, SKILL_DICT,
            ambiguous_for_summary=AMBIGUOUS_FOR_SUMMARY,
            is_noise_fn=is_noise_token,
            alias_to_skill=alias_to,
            summary_kp=summary_kp,
            evidence_id_start=eid,
            context_filters=[context_filter_skill],
            company=r.company if isinstance(r.company, str) else None,
            job_title=r.job_title if isinstance(r.job_title, str) else None,
        )
        for e in evs:
            e["job_link"] = r.job_link
            evidence_rows.append(e)
        for lg in logs:
            lg["job_link"] = r.job_link
            token_logs.append(lg)
            if lg.get("status") == "filtered" and str(lg.get("reason", "")).startswith("context:"):
                filtered_hits.append(lg)
        if evs:
            eid = max(e["evidence_id"] for e in evs) + 1

    evidence = pd.DataFrame(evidence_rows)
    token_log_df = pd.DataFrame(token_logs)
    filtered_df = pd.DataFrame(filtered_hits)

    alias_tables = load_alias_tables(cfg.ALIAS_CSV)
    refined, dropped = refine_skill_table(
        evidence, alias_tables=alias_tables,
        skill_type_map=SKILL_TYPE, domain_map=COURSE_DOMAIN,
        title_by_link=title_by_link, family_by_link=family_by_link,
    )
    refined["job_family"] = refined["job_link"].map(family_by_link)
    ner_only_pct = (refined["evidence_status"] == "ner_only").mean() if len(refined) else 0
    print(f"evidence={len(evidence):,} refined={len(refined):,} ner_only={ner_only_pct:.1%} filtered_hits={len(filtered_df):,}")

    # features + quals
    n_skills_total = refined.groupby("job_link")["skill_refined"].nunique()
    concrete = refined.loc[~refined["is_generic"].astype(bool)]
    n_skills_concrete = concrete.groupby("job_link")["skill_refined"].nunique()
    tok_stats = (
        token_log_df.groupby(["job_link", "status"]).size().unstack(fill_value=0)
        if len(token_log_df) else pd.DataFrame()
    )

    feat_rows, all_yoe, all_edu, all_cert = [], [], [], []
    for r in base.itertuples(index=False):
        quals = extract_quals(
            r.job_summary if isinstance(r.job_summary, str) else "",
            r.job_title if isinstance(r.job_title, str) else "",
        )
        for yr in quals["yoe_rows"]:
            yr = dict(yr); yr["job_link"] = r.job_link; all_yoe.append(yr)
        for er in quals["edu_rows"]:
            er = dict(er); er["job_link"] = r.job_link; all_edu.append(er)
        for cr in quals["cert_rows"]:
            cr = dict(cr); cr["job_link"] = r.job_link; all_cert.append(cr)

        n_tot = int(n_skills_total.get(r.job_link, 0))
        n_con = int(n_skills_concrete.get(r.job_link, 0))
        mapped = int(tok_stats.at[r.job_link, "mapped"]) if len(tok_stats) and r.job_link in tok_stats.index and "mapped" in tok_stats.columns else 0
        unmapped = int(tok_stats.at[r.job_link, "unmapped"]) if len(tok_stats) and r.job_link in tok_stats.index and "unmapped" in tok_stats.columns else 0
        filtered = int(tok_stats.at[r.job_link, "filtered"]) if len(tok_stats) and r.job_link in tok_stats.index and "filtered" in tok_stats.columns else 0
        tstat = text_status_row(r)
        has_skills = isinstance(r.job_skills, str) and bool(r.job_skills.strip())
        has_summ = isinstance(r.job_summary, str) and bool(r.job_summary.strip())
        if tstat != "ok" and n_tot == 0:
            sestatus = "no_text"
        else:
            sestatus = skills_extraction_status(
                has_skills_text=has_skills, has_summary_text=has_summ,
                n_skills=n_tot, n_raw_tokens=mapped + unmapped + filtered,
                n_unmapped_tokens=unmapped,
            )
        feat_rows.append({
            "job_link": r.job_link,
            "job_title": r.job_title,
            "company": r.company,
            "job_location": r.job_location,
            "search_country": r.search_country,
            "job_level": r.job_level,
            "job_type": r.job_type,
            "first_seen": r.first_seen,
            "job_family": family_by_link.get(r.job_link, "Other"),
            "dup_group_id": r.dup_group_id,
            "template_family_id": r.template_family_id,
            "is_dup_primary": r.is_dup_primary,
            "text_status": tstat,
            "has_req_section": quals["has_req_section"],
            "edu_required": quals["edu"]["edu_required"],
            "edu_preferred": quals["edu"]["edu_preferred"],
            "edu_mentioned": quals["edu"]["edu_mentioned"],
            "edu_alternatives": quals["edu"].get("edu_alternatives"),
            "edu_not_required": quals["edu"]["edu_not_required"],
            "edu_status": quals["edu"]["edu_status"],
            "edu_or_equiv": quals["edu"]["edu_or_equiv"],
            "yoe_min_overall": quals["yoe"]["yoe_min_overall"],
            "yoe_max_overall": quals["yoe"]["yoe_max_overall"],
            "yoe_multi": quals["yoe"]["yoe_multi"],
            "yoe_min_any_skill": quals["yoe"].get("yoe_min_any_skill"),
            "yoe_min_required": quals["yoe"].get("yoe_min_required"),
            "yoe_max_required": quals["yoe"].get("yoe_max_required"),
            "yoe_min_preferred": quals["yoe"].get("yoe_min_preferred"),
            "yoe_max_preferred": quals["yoe"].get("yoe_max_preferred"),
            "certifications_pipe": " | ".join(quals["certs"]) if quals["certs"] else None,
            "n_certifications": len(quals["certs"]) if quals["certs"] else None,
            "n_skills_total": n_tot,
            "n_skills_concrete": n_con,
            "skills_extraction_status": sestatus,
        })

    features = pd.DataFrame(feat_rows)
    wide = build_wide_from_long(refined, features["job_link"])
    skill_cols = [c for c in wide.columns if c.startswith("skill_")]
    features["n_skills_displayed"] = features["job_link"].map(
        dict(zip(wide["job_link"], wide[skill_cols].notna().sum(axis=1)))
    ).fillna(0).astype(int)

    # validation (dup-isolated)
    sample = split_validation(features, seed=cfg.VALIDATION_SEED)
    sample = sample.merge(base[["job_link", "job_summary"]], on="job_link", how="left")
    sample["summary_full"] = sample["job_summary"].fillna("")
    sample_out = sample[[
        "job_link", "job_title", "company", "job_family", "search_country",
        "dup_group_id", "split", "full_recall", "text_status",
        "n_skills_total", "n_skills_concrete", "n_skills_displayed",
        "skills_extraction_status",
    ]].sort_values(["split", "job_link"])

    # gold + review templates
    gold = sample_out.merge(sample[["job_link", "summary_full"]], on="job_link")
    gold = gold.rename(columns={"job_family": "job_family_pred"})
    gold["job_family_gold"] = ""
    gold["edu_required_gold"] = ""
    gold["edu_preferred_gold"] = ""
    gold["yoe_overall_gold"] = ""
    gold["certs_required_gold"] = ""
    gold["certs_preferred_gold"] = ""
    gold["gold_skills_all"] = ""
    gold["annotator_notes"] = ""

    tune_meta = sample_out.loc[sample_out["split"] == "tune"]
    tune_links = set(tune_meta["job_link"])
    js_tune = refined[refined["job_link"].isin(tune_links)].copy()
    title_m = dict(zip(tune_meta["job_link"], tune_meta["job_title"]))
    fam_m = dict(zip(tune_meta["job_link"], tune_meta["job_family"]))
    full_m = dict(zip(tune_meta["job_link"], tune_meta["full_recall"]))
    zero_links = tune_links - set(js_tune["job_link"])
    review_parts = []
    if len(js_tune):
        review_parts.append(pd.DataFrame({
            "job_link": js_tune["job_link"].values,
            "job_title": js_tune["job_link"].map(title_m).values,
            "job_family_pred": js_tune["job_link"].map(fam_m).values,
            "full_recall": js_tune["job_link"].map(full_m).values,
            "skill_predicted": js_tune["skill_refined"].values,
            "skill_raw": js_tune["skill_raw"].values,
            "sources": js_tune["sources"].values if "sources" in js_tune.columns else "",
            "evidence": js_tune["evidence"].values if "evidence" in js_tune.columns else None,
            "evidence_ids": js_tune["evidence_ids"].values if "evidence_ids" in js_tune.columns else "",
            "evidence_status": js_tune["evidence_status"].values if "evidence_status" in js_tune.columns else "",
            "sense": js_tune["sense"].values if "sense" in js_tune.columns else "",
            "human_correct": "", "error_type": "", "human_notes": "",
        }))
    if zero_links:
        z = tune_meta[tune_meta["job_link"].isin(zero_links)]
        review_parts.append(pd.DataFrame({
            "job_link": z["job_link"].values, "job_title": z["job_title"].values,
            "job_family_pred": z["job_family"].values, "full_recall": z["full_recall"].values,
            "skill_predicted": "", "skill_raw": "", "sources": "",
            "evidence": "[ZERO OUTPUT]", "evidence_ids": "", "evidence_status": "none",
            "sense": "", "human_correct": "", "error_type": "", "human_notes": "",
        }))
    review_tune = pd.concat(review_parts, ignore_index=True) if review_parts else pd.DataFrame()

    # quals review tune
    feat_tune = features[features["job_link"].isin(tune_links)]
    review_qual = pd.DataFrame({
        "job_link": feat_tune["job_link"].values,
        "job_title": feat_tune["job_title"].values,
        "job_family_pred": feat_tune["job_family"].values,
        "edu_status_pred": feat_tune["edu_status"].values,
        "edu_required_pred": feat_tune["edu_required"].values,
        "edu_preferred_pred": feat_tune["edu_preferred"].values,
        "yoe_min_overall_pred": feat_tune["yoe_min_overall"].values,
        "yoe_max_overall_pred": feat_tune["yoe_max_overall"].values,
        "certs_pred": feat_tune["certifications_pipe"].values,
        "edu_required_gold": "", "edu_preferred_gold": "",
        "yoe_overall_gold": "", "certs_required_gold": "", "certs_preferred_gold": "",
        "error_type": "", "human_notes": "",
    })

    # --- BLOCKING QA (before write) ---
    block, warn = run_qa_v5(
        base, features, refined, dropped, evidence, filtered_df,
        sample_out, gold, review_tune, wide, skill_cols,
    )
    print("\n=== BLOCKING QA ===")
    print(block.to_string(index=False))
    print("\n=== WARNING QA ===")
    print(warn.to_string(index=False))
    if (block["status"] == "FAIL").any():
        print("BLOCKING QA FAILED — no outputs written.", file=sys.stderr)
        block.to_csv(OUT / f"quality_checks_{SUF}_blocking_FAILED.csv", index=False)
        sys.exit(1)

    # --- write outputs ---
    evidence.to_csv(OUT / f"skill_evidence_{SUF}_{TAG}.csv", index=False)
    refined.to_csv(OUT / f"job_skill_refined_{SUF}_{TAG}.csv", index=False)
    dropped.to_csv(OUT / f"skill_dropped_{SUF}_{TAG}.csv", index=False)
    features.to_csv(OUT / f"job_features_{SUF}_{TAG}.csv", index=False)
    wide.to_csv(OUT / f"job_skill_wide_{SUF}_{TAG}.csv", index=False)
    pd.DataFrame(all_yoe).to_csv(OUT / f"job_yoe_{SUF}_{TAG}.csv", index=False)
    pd.DataFrame(all_edu).to_csv(OUT / f"job_edu_{SUF}_{TAG}.csv", index=False)
    pd.DataFrame(all_cert).to_csv(OUT / f"job_cert_{SUF}_{TAG}.csv", index=False)
    token_log_df.to_csv(OUT / f"token_log_{SUF}_{TAG}.csv", index=False)
    filtered_df.to_csv(OUT / f"filtered_hits_{SUF}_{TAG}.csv", index=False)
    family_df.to_csv(OUT / f"job_family_edu_stage1_{SUF}_{TAG}.csv", index=False)

    sample_out.to_csv(OUT / f"validation_sample_{SUF}.csv", index=False)
    sample_out.loc[sample_out["split"] == "tune", ["job_link", "job_family", "dup_group_id", "full_recall"]].to_csv(
        OUT / f"validation_tune_links_{SUF}.csv", index=False
    )
    sample_out.loc[sample_out["split"] == "holdout", ["job_link", "job_family", "dup_group_id"]].to_csv(
        OUT / f"validation_holdout_links_{SUF}.csv", index=False
    )
    gold.to_csv(OUT / f"gold_annotation_template_{SUF}.csv", index=False)
    review_tune.to_csv(OUT / f"review_template_skills_tune_{SUF}.csv", index=False)
    review_qual.to_csv(OUT / f"review_template_qualifications_tune_{SUF}.csv", index=False)
    with open(OUT / f"review_template_skills_holdout_{SUF}.README.txt", "w") as f:
        f.write("Holdout prediction review deferred until tune annotation is done.\n")

    dual = compare_count_modes(refined, features, country=cfg.EDA_DEFAULT_COUNTRY, top_n=40)
    dual.to_csv(OUT / f"skill_top40_dual_counts_{SUF}_{TAG}.csv", index=False)
    dup_group_summary(features, country=cfg.EDA_DEFAULT_COUNTRY).to_csv(
        OUT / f"dup_group_summary_{SUF}_{TAG}.csv", index=False
    )

    # 3 random evidences per top skill
    ev_samples = []
    for skill in dual["skill"].head(40):
        sub = refined.loc[refined["skill_refined"] == skill, ["job_link", "skill_refined", "evidence", "sources"]]
        if len(sub):
            ev_samples.append(sub.sample(n=min(3, len(sub)), random_state=7))
    if ev_samples:
        pd.concat(ev_samples).to_csv(OUT / f"top40_evidence_samples_{SUF}.csv", index=False)

    block.to_csv(OUT / f"quality_checks_{SUF}_blocking.csv", index=False)
    warn.to_csv(OUT / f"quality_checks_{SUF}_warnings.csv", index=False)

    # metrics
    yoe_overall_n = features["yoe_min_overall"].notna().sum()
    print(f"\nyoe_min_overall non-null: {yoe_overall_n} (v4 was 1555 with skill-specific leakage)")
    print(f"yoe_min_any_skill non-null: {features['yoe_min_any_skill'].notna().sum()}")
    print("DONE v8")


def run_qa_v5(base, features, refined, dropped, evidence, filtered_df,
              sample_out, gold, review_tune, wide, skill_cols):
    block, warn = [], []

    def B(name, ok, detail):
        block.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": detail})

    def W(name, detail):
        warn.append({"check": name, "status": "WARN", "detail": detail})

    # unique keys
    B("job_link_unique_features", features["job_link"].is_unique,
      f"dups={features['job_link'].duplicated().sum()}")
    B("job_skill_unique", not refined.duplicated(["job_link", "skill_refined"]).any(),
      f"dups={refined.duplicated(['job_link','skill_refined']).sum()}")
    B("evidence_id_unique", evidence["evidence_id"].is_unique if len(evidence) else True,
      f"dups={evidence['evidence_id'].duplicated().sum() if len(evidence) else 0}")

    # evidence coverage
    chosen = set()
    for s in refined.get("evidence_ids", pd.Series(dtype=str)).dropna():
        chosen.update(str(s).split("|"))
    drop_ids = set(dropped["evidence_id"].astype(str)) if len(dropped) and "evidence_id" in dropped.columns else set()
    all_ids = set(evidence["evidence_id"].astype(str))
    uncovered = all_ids - chosen - drop_ids
    B("evidence_id_coverage", len(uncovered) == 0, f"uncovered={len(uncovered)}")

    # n_skills consistency
    n_long = refined.groupby("job_link")["skill_refined"].nunique()
    m = features[["job_link", "n_skills_total"]].merge(n_long.rename("n"), on="job_link", how="left")
    m["n"] = m["n"].fillna(0).astype(int)
    B("n_skills_total_eq_long", (m["n_skills_total"] == m["n"]).all(),
      f"mismatch={(m['n_skills_total']!=m['n']).sum()}")
    wide_n = wide[skill_cols].notna().sum(axis=1)
    wm = features[["job_link", "n_skills_displayed"]].merge(
        pd.DataFrame({"job_link": wide["job_link"], "wn": wide_n}), on="job_link"
    )
    B("n_skills_displayed_eq_wide", (wm["n_skills_displayed"] == wm["wn"]).all(),
      f"mismatch={(wm['n_skills_displayed']!=wm['wn']).sum()}")

    # sample fixed
    links = set(pd.read_csv(SAMPLE_LINKS)["job_link"])
    B("sample_matches_file", set(features["job_link"]) == links,
      f"feat={len(features)} file={len(links)} symdiff={len(set(features['job_link'])^links)}")

    # validation coverage by SET
    gold_set = set(gold["job_link"])
    sample_set = set(sample_out["job_link"])
    B("gold_set_eq_sample", gold_set == sample_set,
      f"gold={len(gold_set)} sample={len(sample_set)} missing={len(sample_set-gold_set)}")
    tune_set = set(sample_out.loc[sample_out["split"] == "tune", "job_link"])
    rev_set = set(review_tune["job_link"]) if len(review_tune) else set()
    B("review_tune_set_eq_tune", rev_set == tune_set,
      f"review={len(rev_set)} tune={len(tune_set)} missing={len(tune_set-rev_set)}")

    # no dup group leak
    tune_g = set(sample_out.loc[sample_out["split"] == "tune", "dup_group_id"])
    hold_g = set(sample_out.loc[sample_out["split"] == "holdout", "dup_group_id"])
    B("dup_group_no_leak", len(tune_g & hold_g) == 0, f"overlap={len(tune_g & hold_g)}")

    # tighten rules fired
    reasons = filtered_df["reason"].astype(str) if len(filtered_df) and "reason" in filtered_df.columns else pd.Series(dtype=str)
    for label, key in [
        ("filter_supervision_fired", "supervision"),
        ("filter_recruitment_fired", "recruitment"),
        ("filter_nursing_fired", "nursing"),
        ("filter_benefits_fired", "benefits"),
    ]:
        n = int(reasons.str.contains(key, case=False, na=False).sum())
        B(label, n >= 1, f"hits={n}")

    # warnings: boilerplate classify
    if len(evidence):
        has = evidence[evidence["evidence"].notna()]
        for skill, g in has.groupby("skill"):
            if len(g) < 20:
                continue
            top = g["evidence"].astype(str).value_counts(normalize=True).iloc[0]
            if top >= 0.20:
                klass = classify_boilerplate(skill, evidence, features)
                W(f"boilerplate:{skill}", f"share={top:.0%} class={klass}")

    return pd.DataFrame(block), pd.DataFrame(warn)


if __name__ == "__main__":
    main()
