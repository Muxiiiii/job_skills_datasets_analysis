"""Build the small summary tables that EDA and the Streamlit app read.

Reads row-level pipeline output (jobs / job-skills / job-certs parquet) strictly
read-only and writes CSV/JSON summaries to ``--summary-dir``.

    python -m src.analysis.build_summaries                  # pilot: chunks 0-5
    python -m src.analysis.build_summaries --preset full    # after the full run

Conventions (see outputs/summary/DATA_QUALITY.md):
- One posting per ``dup_group_id`` (the ``is_dup_primary`` row, ties by job_link).
- Default skill view excludes ``is_generic`` and ``(unspecified)`` labels.
- Every skill table carries a ``high_confidence`` (two-source) column for contrast.
- Shares are shares of deduplicated postings in the group.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd

from src.analysis.config import QUALITY, QUALITY_NOTE, ROOT, add_input_args, resolve_inputs, sql_list

DIMS = ("position_group", "search_country", "job_level")
EDU_ORDER = ["high_school", "associate", "bachelor", "master", "phd", "professional_doctorate"]


def skill_meta(skills: list[str]) -> pd.DataFrame:
    """skill -> (skill_type, domain) from the frozen extraction vocabulary (import only)."""
    type_map, domain_map, sense = {}, {}, {}
    try:
        sys.path.insert(0, str(ROOT))
        from extraction_resources import COURSE_DOMAIN, SKILL_TYPE
        type_map, domain_map = SKILL_TYPE, COURSE_DOMAIN
        from skill_refinement import SENSE_META
        sense = SENSE_META
    except Exception as exc:  # vocabulary not importable: fall back to hard/Other
        print(f"  warn: skill vocabulary import failed ({exc}); using defaults")
    rows = []
    for s in skills:
        base = re.sub(r"\s*\((?:unspecified|conflict)\)$", "", s)
        if s in sense:
            t, d = sense[s]
        elif base in type_map:
            t, d = type_map[base], domain_map.get(base, "Other")
        else:
            base2 = re.sub(r"\s*\(.*\)$", "", s)
            t, d = type_map.get(base2, "hard"), domain_map.get(base2, "Other")
        rows.append({"skill": s, "skill_type": t, "domain": d})
    return pd.DataFrame(rows)


def connect(inp: dict) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute("SET memory_limit='2GB'; SET threads=4")
    con.execute(f"""
        CREATE TEMP TABLE jobs_all AS
        SELECT * FROM read_parquet({sql_list(inp['jobs'])})
    """)
    # One posting per dup group. Groups are assigned per chunk, so a group can
    # carry more than one "primary" across chunks — pick a single row here.
    con.execute("""
        CREATE TEMP TABLE jobs AS
        SELECT * EXCLUDE (rn) FROM (
            SELECT *, row_number() OVER (
                PARTITION BY dup_group_id
                ORDER BY is_dup_primary DESC, job_link) AS rn
            FROM jobs_all)
        WHERE rn = 1
    """)
    con.execute(f"""
        CREATE TEMP TABLE skills_all AS
        SELECT DISTINCT job_link, skill,
               coalesce(is_generic, false) OR skill LIKE '%(unspecified)%' AS generic,
               coalesce(high_confidence, false) AS hc
        FROM read_parquet({sql_list(inp['skills'])})
    """)
    con.execute("""
        CREATE TEMP TABLE sk AS
        SELECT s.*, j.position_group, j.search_country, j.job_level
        FROM skills_all s JOIN jobs j USING (job_link)
    """)
    con.execute(f"""
        CREATE TEMP TABLE certs AS
        SELECT DISTINCT c.job_link, c.cert, c.cert_status, j.position_group, j.search_country
        FROM read_parquet({sql_list(inp['certs'])}) c JOIN jobs j USING (job_link)
    """)
    return con


def build(inp: dict, top_n: int = 200) -> dict:
    out: Path = Path(inp["summary_dir"])
    out.mkdir(parents=True, exist_ok=True)
    con = connect(inp)
    q = lambda sql: con.execute(sql).df()  # noqa: E731
    n_all = con.execute("SELECT count(*) FROM jobs_all").fetchone()[0]
    n_jobs = con.execute("SELECT count(*) FROM jobs").fetchone()[0]

    # --- posting counts per dimension (denominators) ---------------------------------
    cube = q(f"SELECT {', '.join(DIMS)}, count(*) AS n_jobs FROM jobs GROUP BY ALL")
    cube.to_csv(out / "jobs_cube.csv", index=False)
    parts = []
    for dim in DIMS + ("job_type", "text_status"):
        d = q(f"""
            SELECT '{dim}' AS dim, a.{dim} AS value, count(*) AS n_jobs_with_dups,
                   count(*) FILTER (WHERE j.job_link IS NOT NULL) AS n_jobs
            FROM jobs_all a LEFT JOIN jobs j USING (job_link) GROUP BY ALL ORDER BY n_jobs DESC
        """)
        parts.append(d)
    jobs_by_dim = pd.concat(parts, ignore_index=True)
    jobs_by_dim["share_jobs"] = jobs_by_dim["n_jobs"] / n_jobs
    jobs_by_dim.to_csv(out / "jobs_by_dim.csv", index=False)

    # --- skill frequency ------------------------------------------------------------
    freq_all = q(f"""
        SELECT s.skill, bool_or(s.generic) AS is_generic,
               count(*) AS n_jobs, count(*) / {n_jobs}::DOUBLE AS share_jobs,
               count(*) FILTER (WHERE hc) AS n_jobs_hc,
               count(*) FILTER (WHERE hc) / {n_jobs}::DOUBLE AS share_jobs_hc
        FROM sk s GROUP BY 1 ORDER BY n_jobs DESC
    """)
    with_dups = q(f"""
        SELECT skill, count(*) AS n_jobs_with_dups, count(*) / {n_all}::DOUBLE AS share_jobs_with_dups
        FROM skills_all WHERE NOT generic GROUP BY 1
    """)
    meta = skill_meta(freq_all["skill"].tolist())
    meta.to_csv(out / "skill_meta.csv", index=False)
    freq_all = freq_all.merge(meta, on="skill").merge(with_dups, on="skill", how="left")
    freq_all.to_csv(out / "skill_freq_overall_incl_generic.csv", index=False)
    # default view: only non-generic mentions (the generic flag is per mention, not per skill)
    freq = q(f"""
        SELECT skill, count(*) AS n_jobs, count(*) / {n_jobs}::DOUBLE AS share_jobs,
               count(*) FILTER (WHERE hc) AS n_jobs_hc,
               count(*) FILTER (WHERE hc) / {n_jobs}::DOUBLE AS share_jobs_hc
        FROM sk WHERE NOT generic GROUP BY 1 ORDER BY n_jobs DESC
    """).merge(meta, on="skill").merge(with_dups, on="skill", how="left")
    freq["rank"] = freq["n_jobs"].rank(ascending=False, method="first").astype(int)
    freq["rank_hc"] = freq["n_jobs_hc"].rank(ascending=False, method="first").astype(int)
    freq.to_csv(out / "skill_freq_overall.csv", index=False)

    for dim in DIMS:
        d = q(f"""
            WITH den AS (SELECT {dim} AS dim, count(*) AS n_dim FROM jobs GROUP BY 1)
            SELECT s.{dim} AS {dim}, s.skill, count(*) AS n_jobs,
                   count(*) / any_value(den.n_dim)::DOUBLE AS share_jobs,
                   count(*) FILTER (WHERE hc) AS n_jobs_hc,
                   count(*) FILTER (WHERE hc) / any_value(den.n_dim)::DOUBLE AS share_jobs_hc,
                   any_value(den.n_dim) AS n_jobs_in_group
            FROM sk s JOIN den ON s.{dim} = den.dim
            WHERE NOT s.generic GROUP BY 1, 2 ORDER BY 1, n_jobs DESC
        """)
        # lift vs overall share: >1 means over-represented in this group
        d = d.merge(freq[["skill", "share_jobs"]].rename(columns={"share_jobs": "share_overall"}), on="skill")
        d["lift_vs_overall"] = d["share_jobs"] / d["share_overall"]
        d.to_csv(out / f"skill_freq_by_{dim}.csv", index=False)

    # cube for arbitrary filter combinations in the dashboard
    q(f"""
        SELECT {', '.join(DIMS)}, skill, count(*) AS n_jobs, count(*) FILTER (WHERE hc) AS n_jobs_hc
        FROM sk WHERE NOT generic GROUP BY ALL
    """).to_csv(out / "skill_freq_cube.csv", index=False)

    # --- co-occurrence and lift among top-N skills -------------------------------------
    top = freq.head(top_n)["skill"].tolist()
    con.register("top_skills", pd.DataFrame({"skill": top}))
    co = q(f"""
        WITH t AS (SELECT job_link, skill FROM sk WHERE NOT generic AND skill IN (SELECT skill FROM top_skills)),
             m AS (SELECT skill, count(*) AS n FROM t GROUP BY 1),
             co AS (SELECT a.skill AS skill_a, b.skill AS skill_b, count(*) AS n_co
                    FROM t a JOIN t b ON a.job_link = b.job_link AND a.skill < b.skill GROUP BY 1, 2)
        SELECT co.skill_a, co.skill_b, co.n_co, ma.n AS n_a, mb.n AS n_b, {n_jobs} AS n_jobs,
               co.n_co * {n_jobs}::DOUBLE / (ma.n * mb.n) AS lift,
               co.n_co / (ma.n + mb.n - co.n_co)::DOUBLE AS jaccard
        FROM co JOIN m ma ON co.skill_a = ma.skill JOIN m mb ON co.skill_b = mb.skill
        ORDER BY n_co DESC
    """)
    co.to_csv(out / f"skill_cooccurrence_top{top_n}.csv", index=False)

    # --- education / experience -------------------------------------------------------
    q(f"""SELECT {', '.join(DIMS)}, coalesce(edu_required, 'not_stated') AS edu_required, count(*) AS n_jobs
          FROM jobs GROUP BY ALL""").to_csv(out / "edu_dist.csv", index=False)
    q(f"""SELECT {', '.join(DIMS)}, yoe_min_overall, count(*) AS n_jobs
          FROM jobs GROUP BY ALL""").to_csv(out / "yoe_dist.csv", index=False)

    # --- single-certificate occurrence rates ------------------------------------------------
    cert = q(f"""
        SELECT cert, count(DISTINCT job_link) AS n_jobs,
               count(DISTINCT job_link) / {n_jobs}::DOUBLE AS share_jobs,
               count(DISTINCT job_link) FILTER (WHERE cert_status = 'required') AS n_jobs_required
        FROM certs GROUP BY 1 ORDER BY n_jobs DESC
    """)
    cert.to_csv(out / "cert_occurrence.csv", index=False)
    q("""
        WITH den AS (SELECT position_group, count(*) AS n_dim FROM jobs GROUP BY 1)
        SELECT c.position_group, c.cert, count(DISTINCT c.job_link) AS n_jobs,
               count(DISTINCT c.job_link) / any_value(den.n_dim)::DOUBLE AS share_jobs
        FROM certs c JOIN den USING (position_group) GROUP BY 1, 2 ORDER BY 1, n_jobs DESC
    """).to_csv(out / "cert_by_position_group.csv", index=False)

    # --- soft vs hard ---------------------------------------------------------------------
    con.register("meta", meta)
    soft = q("""
        WITH x AS (SELECT s.job_link, s.position_group, m.skill_type
                   FROM sk s JOIN meta m USING (skill) WHERE NOT s.generic),
             per_job AS (SELECT job_link, any_value(position_group) AS position_group,
                                count(*) FILTER (WHERE skill_type = 'soft') AS n_soft,
                                count(*) FILTER (WHERE skill_type <> 'soft') AS n_hard
                         FROM x GROUP BY 1)
        SELECT position_group, count(*) AS n_jobs_with_skills,
               sum(n_soft) AS soft_mentions, sum(n_hard) AS hard_mentions,
               sum(n_soft) / sum(n_soft + n_hard)::DOUBLE AS soft_share_of_mentions,
               avg((n_soft > 0)::INT) AS share_jobs_any_soft,
               avg((n_hard > 0)::INT) AS share_jobs_any_hard
        FROM per_job GROUP BY ROLLUP (position_group) ORDER BY n_jobs_with_skills DESC
    """)
    soft["position_group"] = soft["position_group"].fillna("ALL")
    soft.to_csv(out / "soft_hard_by_position_group.csv", index=False)

    # --- overview ------------------------------------------------------------------------
    per_job = q("SELECT count(*) AS n FROM sk WHERE NOT generic GROUP BY job_link")["n"]
    per_job_all = q("SELECT count(*) AS n FROM sk GROUP BY job_link")["n"]
    nn = con.execute("""SELECT avg((edu_required IS NOT NULL)::INT), avg((yoe_min_overall IS NOT NULL)::INT),
                               median(yoe_min_overall), avg((text_status = 'ok')::INT) FROM jobs""").fetchone()
    overview = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "inputs": {k: [str(Path(p).relative_to(ROOT)) if Path(p).is_relative_to(ROOT) else str(p)
                       for p in inp[k]] for k in ("jobs", "skills", "certs")},
        "n_postings_raw": int(n_all),
        "n_postings_dedup": int(n_jobs),
        "dup_share": 1 - n_jobs / n_all,
        "n_distinct_skills": int(len(freq_all)),
        "n_distinct_skills_specific": int(len(freq)),
        "share_jobs_with_any_specific_skill": float(len(per_job) / n_jobs),
        "skills_per_job_mean_specific": float(per_job.mean()),
        "skills_per_job_median_specific": float(per_job.median()),
        "skills_per_job_mean_incl_generic": float(per_job_all.mean()),
        "share_skill_rows_high_conf": float(con.execute("SELECT avg(hc::INT) FROM sk WHERE NOT generic").fetchone()[0]),
        "share_jobs_edu_stated": float(nn[0]),
        "share_jobs_yoe_stated": float(nn[1]),
        "yoe_median_when_stated": float(nn[2]),
        "share_jobs_text_ok": float(nn[3]),
        "n_distinct_certs": int(len(cert)),
        "share_jobs_any_cert": float(con.execute("SELECT count(DISTINCT job_link) FROM certs").fetchone()[0] / n_jobs),
        "by_country": {r.value: int(r.n_jobs) for r in jobs_by_dim[jobs_by_dim.dim == "search_country"].itertuples()},
        "cooccurrence_top_n": top_n,
        "quality": QUALITY,
        "quality_note": QUALITY_NOTE,
    }
    (out / "overview.json").write_text(json.dumps(overview, indent=2, ensure_ascii=False))
    con.close()
    return overview


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_input_args(ap)
    ap.add_argument("--top-n", type=int, default=200, help="skills in the co-occurrence table")
    args = ap.parse_args(argv)
    inp = resolve_inputs(args)
    ov = build(inp, args.top_n)
    print(json.dumps({k: v for k, v in ov.items() if k not in ("inputs", "quality")}, indent=2, ensure_ascii=False))
    print("done →", inp["summary_dir"])


if __name__ == "__main__":
    main()
