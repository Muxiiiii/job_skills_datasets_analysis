# LinkedIn skill-demand analysis

What do employers actually ask for? This project extracts skills, education, experience and
certificate requirements from ~1.35M LinkedIn job postings and summarises **demand-side skill
patterns** by occupation group, country and seniority, with a Streamlit dashboard on top.

> **Status.** The full 1.35M-posting run is still in progress. Everything under
> `outputs/summary/pilot/`, `outputs/figures/`, and the two reports is built from the **first
> 300,000 postings** (259,589 after deduplication). That slice is *not* a random sample —
> see [Pilot caveat](#pilot-caveat). All scripts take input paths as arguments, so the same
> commands re-run on the full output.

## Data

[1.3M LinkedIn Jobs & Skills (2024)](https://www.kaggle.com/datasets/asaniczka/1-3m-linkedin-jobs-and-skills-2024)
from Kaggle: `linkedin_job_postings.csv`, `job_skills.csv`, `job_summary.csv`
(US, UK, Canada, Australia). Raw data and row-level outputs are **not** in this repository;
only small aggregated tables are.

## Pipeline

| Stage | Code | Output |
|---|---|---|
| Clean + join the three CSVs | `01_`–`03_*.ipynb` | `cleaned/jobs_combined.parquet` |
| Rule-based extraction (frozen v8, see [`CHANGELOG.md`](CHANGELOG.md)) | `run_pipeline_v8.py`, `extraction_resources.py`, `skill_refinement.py` | per posting: skills (with source + evidence), `edu_required`, `yoe_min_overall`, certificates |
| Occupation grouping | `search_position_groups.py`, `config/search_position_groups.csv` | 1,993 LinkedIn `search_position` values → 12 groups + Other |
| Full run (chunked, resumable) | `run_full_v8.py` | `outputs/full_v8/` |
| Summary tables | `src/analysis/build_summaries.py` | `outputs/summary/<name>/*.csv` |
| EDA | `src/analysis/eda.py` | `outputs/figures/*.png`, [`outputs/eda_report.md`](outputs/eda_report.md) |
| Models | `src/analysis/models.py` | [`outputs/models_report.md`](outputs/models_report.md) |
| Dashboard | `app/streamlit_app.py` | reads the summary tables only |

Skills come from two sources: LinkedIn's own `job_skills` list and a dictionary/context match on
the description text. A skill found in **both** is flagged `high_confidence`.

## Validation

Rules were tuned on 150 labelled postings, checked on a 50-posting holdout, then **frozen**.
The headline numbers come from **50 fresh postings** drawn after the freeze and labelled blind
(gold file hashed before the pipeline was run). Gold labels were produced by an LLM annotator
(Claude) reading each posting in full, not by the pipeline. Details:
[`cleaned/final_eval_v8.md`](cleaned/final_eval_v8.md) and [`cleaned/holdout_eval_v7.md`](cleaned/holdout_eval_v7.md).

| Field | Fresh-50 result | How it is used |
|---|---|---|
| Skills | precision **0.66**, recall **0.58** | Rankings and group comparisons — not exact per-posting lists |
| Skills, high-confidence subset | precision **0.93** | Conservative contrast shown next to every ranking |
| `edu_required` | accuracy **0.86** | Used; often simply not stated |
| `yoe_min_overall` | accuracy **0.84** | Used; errors are mostly missed values |
| Certificates (exact set) | 0.56 | Not used as a set — single-certificate occurrence rates only |
| `job_family_pred` | 0.62 | Experimental, **not used**; grouping relies on `search_position` |

Defaults in every table: one posting per `dup_group_id`; generic labels (`is_generic`,
`(unspecified)`) excluded; shares are over deduplicated postings in the group.

## Pilot results (300k slice)

- **Soft skills dominate the top of the ranking**: Communication 47.9% and Teamwork 39.1% of postings; 7 of the top 10 skills are soft. The most common non-soft skill is workplace safety (17.9%).
- **Each occupation group has a signature**: Litigation appears in 45.5% of legal postings (40× the overall rate), Food Preparation in 33.6% of hospitality postings (19×), Nursing in 83.6% of nursing postings.
- **Soft/hard mix varies by group**: soft skills are 40.5% of skill mentions overall, from 30.7% in tech/engineering to 60.5% in legal.
- **Formal requirements are often unstated**: 22.3% of postings state a degree (of those, 75.9% ask for a bachelor's or higher) and 30.6% state years of experience (median 3).
- **Certificates**: a driver's licence is the most requested credential (9.2%), then RN (4.4%) and CPR (2.1%).
- **Models**: a logistic regression on the skill set alone predicts the 12 occupation groups with accuracy 0.44 / macro-F1 0.44 (majority baseline 0.28 / 0.04). Nursing (F1 0.73) and finance (0.68) are recognisable from skills; the broad management/admin group is not (0.25). Skill clusters are soft themes, not well-separated groups (silhouette ≈ 0.06).

### Pilot caveat

The full run processes postings in `job_link` order. In the first 300k rows Australia, Canada and
the UK are essentially complete, but the **US covers only job titles early in the alphabet** and
makes up ~32% of the slice versus ~85% of the corpus. Overall and US figures will move when the
full run is summarised; within-group patterns for AU/CA/UK are the most reliable part.

## Run it

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# dashboard (uses the committed pilot summaries)
streamlit run app/streamlit_app.py

# rebuild everything from row-level output (needs outputs/full_v8/)
python -m src.analysis.build_summaries            # pilot: chunks 0-5 → outputs/summary/pilot
python -m src.analysis.eda                        # figures + outputs/eda_report.md
python -m src.analysis.models                     # outputs/models_report.md

# after the full run has merged its chunks
python -m src.analysis.build_summaries --preset full
python -m src.analysis.eda --summary-dir outputs/summary/full --figures-dir outputs/figures_full --report outputs/eda_report_full.md
python -m src.analysis.models --preset full --report outputs/models_report_full.md
SKILL_SUMMARY_DIR=outputs/summary/full streamlit run app/streamlit_app.py

pytest
```

Any script also accepts explicit `--jobs / --skills / --certs / --summary-dir` paths.

## Dashboard

`app/streamlit_app.py` has seven pages: Overview · Skill ranking (filter by occupation group,
country, level, skill type, high-confidence only) · Co-occurrence (lift) · Education & experience ·
Certificates · Model results · Data quality. It reads only `outputs/summary/pilot/` (override
with `SKILL_SUMMARY_DIR` or the sidebar), so it deploys to Streamlit Community Cloud as-is with
main file `app/streamlit_app.py`.

## Repository layout

```
README.md, CHANGELOG.md       overview; how the rules evolved up to the v8 freeze
requirements.txt
01_–03_*.ipynb                data preparation: overview, join, combine + clean
run_pipeline_v8.py            frozen extraction pipeline (sample run)
run_full_v8.py                chunked, resumable full run
extraction_resources.py       dictionaries + education / experience / certificate rules
skill_refinement.py           section typing, skill evidence, disambiguation, aliases
skill_alias.csv               skill merge / hierarchy table
job_family_classifier.py      experimental job-family model (not used in the analysis)
search_position_groups.py     search_position → occupation group mapping
config_v4.py, eda_counts_v4.py, quality_checks_v3.py   shared paths, counting and QA helpers
RULES_FROZEN_v8.txt           freeze marker for the v8 rules
config/                       search_position_groups.csv (reviewable mapping)
scripts/eval_tune_v6.py       metric definitions used in the validation reports
src/analysis/                 config, build_summaries, eda, models
app/streamlit_app.py          dashboard
tests/                        rule tests + analysis-layer tests
cleaned/                      validation reports, gold labels, frozen job-family model (data files ignored)
outputs/summary/pilot/        small aggregated tables (committed)
outputs/summary/              DATA_QUALITY.md, search_position counts
outputs/figures/              EDA figures
outputs/eda_report.md, outputs/models_report.md
```

Module suffixes (`_v3`, `_v4`, `_v6`) mark the round in which a helper was last changed; they are
all part of the current v8 pipeline.
