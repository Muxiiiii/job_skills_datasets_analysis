"""
Full-corpus v8 extraction (chunked, resumable).

- Does NOT retrain / overwrite frozen job_family joblib.
- Primary grouping: search_position → position_group (config/search_position_groups.csv).
- job_family_pred kept as experimental (title rules; ~0.6 accuracy per final_eval_v8.md).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import sys
import time
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
    context_filter_skill,
    skills_extraction_status,
)
from skill_refinement import (
    assign_job_family_detailed,
    build_alias_to_skill,
    build_summary_keyword_processor,
    extract_skill_evidence,
    load_alias_tables,
    refine_skill_table,
)
from run_pipeline_v8 import assign_dup_ids, extract_quals, is_noise_token, text_status_row
from search_position_groups import build_mapping_csv, load_group_map, CONFIG_CSV

OUT = Path("outputs/full_v8")
CHUNKS = OUT / "chunks"
SUMMARY = Path("outputs/summary")
STATE = OUT / "run_state.json"


def _rss_mb() -> float:
    # macOS ru_maxrss is bytes; Linux is KB
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        return rss / (1024 * 1024)
    return rss / 1024


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def assert_frozen_model_untouched(before: str | None = None) -> str:
    from job_family_classifier import MODEL_PATH
    if not MODEL_PATH.exists():
        raise SystemExit(f"Frozen model missing: {MODEL_PATH}")
    after = _sha256(MODEL_PATH)
    if before is not None and before != after:
        raise SystemExit(f"Frozen model hash changed! before={before} after={after}")
    return after


def load_chunk(offset: int, limit: int) -> pd.DataFrame:
    con = duckdb.connect()
    df = con.execute(
        """
        SELECT *
        FROM read_parquet(?)
        ORDER BY job_link
        LIMIT ? OFFSET ?
        """,
        [str(cfg.JOBS_COMBINED), limit, offset],
    ).df()
    con.close()
    return df


def process_chunk(base: pd.DataFrame, group_map: dict[str, str], *, eid_start: int = 1) -> dict:
    base = assign_dup_ids(base)
    base["position_group"] = base["search_position"].map(
        lambda x: group_map.get(str(x), "Other") if pd.notna(x) else "Other"
    )
    # Experimental family (title rules only — classifier ineffective at scale)
    fam = [assign_job_family_detailed(t if isinstance(t, str) else "")["job_family"]
           for t in base["job_title"]]
    base["job_family_pred"] = fam
    family_by_link = dict(zip(base["job_link"], base["job_family_pred"]))
    title_by_link = dict(zip(base["job_link"], base["job_title"]))

    alias_to = build_alias_to_skill(SKILL_DICT)
    summary_kp = build_summary_keyword_processor(SKILL_DICT, AMBIGUOUS_FOR_SUMMARY)
    evidence_rows = []
    eid = eid_start
    for r in base.itertuples(index=False):
        evs, _ = extract_skill_evidence(
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
        if evs:
            eid = max(e["evidence_id"] for e in evs) + 1

    evidence = pd.DataFrame(evidence_rows) if evidence_rows else pd.DataFrame()
    alias_tables = load_alias_tables(cfg.ALIAS_CSV)
    if len(evidence):
        refined, _ = refine_skill_table(
            evidence, alias_tables=alias_tables,
            skill_type_map=SKILL_TYPE, domain_map=COURSE_DOMAIN,
            title_by_link=title_by_link, family_by_link=family_by_link,
        )
    else:
        refined = pd.DataFrame()

    job_rows, skill_rows, cert_rows = [], [], []
    for r in base.itertuples(index=False):
        quals = extract_quals(
            r.job_summary if isinstance(r.job_summary, str) else "",
            r.job_title if isinstance(r.job_title, str) else "",
        )
        edu, yoe = quals["edu"], quals["yoe"]
        job_rows.append({
            "job_link": r.job_link,
            "job_title": r.job_title,
            "company": r.company,
            "search_country": r.search_country,
            "search_position": r.search_position,
            "position_group": r.position_group,
            "job_level": r.job_level,
            "job_type": r.job_type,
            "dup_group_id": r.dup_group_id,
            "is_dup_primary": r.is_dup_primary,
            "text_status": text_status_row(r),
            "edu_required": edu.get("edu_required"),
            "edu_preferred": edu.get("edu_preferred"),
            "yoe_min_overall": yoe.get("yoe_min_overall"),
            "yoe_min_preferred": yoe.get("yoe_min_preferred"),
            "job_family_pred": r.job_family_pred,  # experimental ~0.6
        })
        for cr in quals["cert_rows"]:
            if cr.get("source_field") == "title" and cr.get("cert_status") == "title_mention":
                continue
            status = cr.get("cert_status") or "mentioned"
            if status == "title_mention":
                continue
            cert_rows.append({
                "job_link": r.job_link,
                "cert": cr.get("certification"),
                "cert_status": "preferred" if status == "preferred" else (
                    "required" if status == "required" else "mentioned"
                ),
            })

    if len(refined):
        for row in refined.itertuples(index=False):
            sources = str(getattr(row, "sources", "") or "")
            # high_confidence: two sources (pipe-joined) OR ≥2 evidence hits
            n_ev = int(getattr(row, "n_evidence", 1) or 1)
            src_l = sources.lower()
            two_src = ("|" in sources) or (
                ("summary" in src_l) and ("skill" in src_l or "ner" in src_l)
            )
            skill_rows.append({
                "job_link": row.job_link,
                "skill": getattr(row, "skill_refined", None) or getattr(row, "skill", None),
                "sources": sources,
                "evidence_status": getattr(row, "evidence_status", None),
                "is_generic": bool(getattr(row, "is_generic", False)),
                "high_confidence": bool(two_src or n_ev >= 2),
            })

    return {
        "jobs": pd.DataFrame(job_rows),
        "skills": pd.DataFrame(skill_rows),
        "certs": pd.DataFrame(cert_rows),
        "next_eid": eid,
    }


def write_chunk(idx: int, out: dict):
    CHUNKS.mkdir(parents=True, exist_ok=True)
    out["jobs"].to_parquet(CHUNKS / f"jobs_chunk_{idx:04d}.parquet", index=False)
    out["skills"].to_parquet(CHUNKS / f"skills_chunk_{idx:04d}.parquet", index=False)
    out["certs"].to_parquet(CHUNKS / f"certs_chunk_{idx:04d}.parquet", index=False)


def load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"completed_chunks": [], "next_offset": 0, "next_eid": 1}


def save_state(st: dict):
    OUT.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, indent=2))


def merge_chunks(pattern: str, dest: Path):
    files = sorted(CHUNKS.glob(pattern))
    if not files:
        raise SystemExit(f"No chunks matching {pattern}")
    paths = ", ".join("'" + str(f).replace("'", "''") + "'" for f in files)
    con = duckdb.connect()
    dest.parent.mkdir(parents=True, exist_ok=True)
    con.execute(
        f"COPY (SELECT * FROM read_parquet([{paths}])) TO '{dest}' (FORMAT PARQUET)"
    )
    con.close()
    return dest


def null_rates(df: pd.DataFrame, cols: list[str]) -> dict:
    out = {}
    for c in cols:
        if c not in df.columns:
            out[c] = None
            continue
        out[c] = float(df[c].isna().mean()) if len(df) else 1.0
    return out


def load_pilot_sample(n: int, seed: int = 42) -> pd.DataFrame:
    """Country-stratified-ish random sample (not ORDER BY job_link — that biases AU/CA URLs)."""
    con = duckdb.connect()
    df = con.execute(
        """
        SELECT * FROM read_parquet(?)
        USING SAMPLE ? PERCENT
        """,
        # fallback: hash sample for reproducibility
        [str(cfg.JOBS_COMBINED), max(1, int(100 * n / 1_300_000))],
    ).df()
    con.close()
    if len(df) < n:
        con = duckdb.connect()
        df = con.execute(
            """
            SELECT * FROM (
              SELECT *, hash(job_link) AS h
              FROM read_parquet(?)
            )
            ORDER BY h
            LIMIT ?
            """,
            [str(cfg.JOBS_COMBINED), n],
        ).df()
        con.close()
    return df.head(n).drop(columns=["h"], errors="ignore")


def run_pilot(n: int = 50_000):
    print(f"=== pilot {n:,} (hash-sampled, not URL-ordered) ===")
    model_hash = assert_frozen_model_untouched()
    build_mapping_csv()
    group_map = load_group_map()
    t0 = time.time()
    base = load_pilot_sample(n)
    peak0 = _rss_mb()
    out = process_chunk(base, group_map)
    elapsed = time.time() - t0
    peak = max(peak0, _rss_mb())
    assert_frozen_model_untouched(model_hash)

    jobs, skills = out["jobs"], out["skills"]
    sample_path = cfg.CLEANED / "job_features_v8_sample5000.csv"
    cmp = {}
    if sample_path.exists():
        s5 = pd.read_csv(sample_path)
        cmp = {
            "sample5k_edu_nonnull": float(s5["edu_required"].notna().mean()) if "edu_required" in s5 else None,
            "pilot_edu_nonnull": float(jobs["edu_required"].notna().mean()),
            "sample5k_yoe_nonnull": float(s5["yoe_min_overall"].notna().mean()) if "yoe_min_overall" in s5 else None,
            "pilot_yoe_nonnull": float(jobs["yoe_min_overall"].notna().mean()),
            "sample5k_country": s5["search_country"].value_counts(normalize=True).head(4).to_dict()
            if "search_country" in s5.columns else None,
            "pilot_country": jobs["search_country"].value_counts(normalize=True).head(4).to_dict(),
        }

    skills_per = skills.groupby("job_link").size() if len(skills) else pd.Series(dtype=float)
    report = {
        "n_jobs": len(jobs),
        "elapsed_sec": round(elapsed, 1),
        "peak_rss_mb": round(peak, 1),
        "jobs_per_sec": round(len(jobs) / elapsed, 2) if elapsed else None,
        "null_rates": null_rates(jobs, [
            "edu_required", "edu_preferred", "yoe_min_overall", "yoe_min_preferred",
            "search_position", "position_group", "job_level", "job_type", "search_country",
        ]),
        "mean_skills_per_job": float(skills_per.mean()) if len(skills_per) else 0.0,
        "median_skills_per_job": float(skills_per.median()) if len(skills_per) else 0.0,
        "position_group_dist": jobs["position_group"].value_counts().head(15).to_dict(),
        "country_dist": jobs["search_country"].value_counts().to_dict(),
        "vs_sample5k": cmp,
        "frozen_model_sha256": model_hash,
        "note": "pilot is hash-sampled; full run processes entire corpus by job_link order",
    }
    SUMMARY.mkdir(parents=True, exist_ok=True)
    (SUMMARY / "pilot_50k_report.json").write_text(json.dumps(report, indent=2))
    pilot_dir = OUT / "pilot"
    pilot_dir.mkdir(parents=True, exist_ok=True)
    out["jobs"].to_parquet(pilot_dir / "jobs_pilot50k.parquet", index=False)
    out["skills"].to_parquet(pilot_dir / "skills_pilot50k.parquet", index=False)
    out["certs"].to_parquet(pilot_dir / "certs_pilot50k.parquet", index=False)
    print(json.dumps(report, indent=2))
    return report


def run_full(chunk_size: int = 100_000, start_offset: int | None = None):
    print("=== full run ===")
    model_hash = assert_frozen_model_untouched()
    if not CONFIG_CSV.exists():
        build_mapping_csv()
    group_map = load_group_map()

    con = duckdb.connect()
    total = con.execute("SELECT count(*) FROM read_parquet(?)", [str(cfg.JOBS_COMBINED)]).fetchone()[0]
    con.close()

    st = load_state()
    offset = st["next_offset"] if start_offset is None else start_offset
    eid = st.get("next_eid", 1)
    completed = set(st.get("completed_chunks", []))
    t_all = time.time()

    while offset < total:
        idx = offset // chunk_size
        chunk_path = CHUNKS / f"jobs_chunk_{idx:04d}.parquet"
        if idx in completed and chunk_path.exists():
            print(f"skip chunk {idx} (already done)")
            offset += chunk_size
            continue
        print(f"chunk {idx}: offset={offset} limit={chunk_size} rss={_rss_mb():.0f}MB")
        t0 = time.time()
        base = load_chunk(offset, chunk_size)
        if len(base) == 0:
            break
        out = process_chunk(base, group_map, eid_start=eid)
        write_chunk(idx, out)
        eid = out["next_eid"]
        completed.add(idx)
        offset += len(base)
        st = {
            "completed_chunks": sorted(completed),
            "next_offset": offset,
            "next_eid": eid,
            "total": total,
            "frozen_model_sha256": model_hash,
        }
        save_state(st)
        assert_frozen_model_untouched(model_hash)
        print(f"  wrote chunk {idx} n={len(base)} in {time.time()-t0:.1f}s")

    # merge
    OUT.mkdir(parents=True, exist_ok=True)
    print("merging chunks…")
    merge_chunks("jobs_chunk_*.parquet", OUT / "jobs_v8.parquet")
    merge_chunks("skills_chunk_*.parquet", OUT / "job_skills_v8.parquet")
    merge_chunks("certs_chunk_*.parquet", OUT / "job_certs_v8.parquet")
    assert_frozen_model_untouched(model_hash)
    print(f"DONE full in {time.time()-t_all:.0f}s model_sha={model_hash[:16]}…")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", type=int, default=0, help="run pilot N jobs (e.g. 50000)")
    ap.add_argument("--full", action="store_true", help="run/resume full corpus")
    ap.add_argument("--chunk-size", type=int, default=100_000)
    ap.add_argument("--reset", action="store_true", help="clear resume state (not chunk files)")
    args = ap.parse_args()
    if args.reset and STATE.exists():
        STATE.unlink()
        print("cleared run_state.json")
    if args.pilot:
        run_pilot(args.pilot)
    if args.full:
        run_full(chunk_size=args.chunk_size)
    if not args.pilot and not args.full:
        ap.print_help()


if __name__ == "__main__":
    main()
