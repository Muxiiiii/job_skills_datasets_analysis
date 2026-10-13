# Changelog

How the extraction pipeline got to the frozen v8 rules. Only the final version (`run_pipeline_v8.py`)
is kept in the repository; earlier versions are summarised here.

Metrics below are on the **tune set** (150 labelled postings) unless stated otherwise. They are
optimistic by construction — the numbers to quote are the post-freeze fresh-50 results in
[`cleaned/final_eval_v8.md`](cleaned/final_eval_v8.md).

| Version | Skill precision | Skill recall | `edu_required` | `yoe_overall` | Certificates (exact set) |
|---|---|---|---|---|---|
| v5 | 0.721 | 0.481 | 0.593 | 0.673 | 0.653 |
| v6 | 0.777 | 0.467 | 0.807 | 0.807 | 0.753 |
| v7 | 0.768 | 0.609 | 0.807 | 0.807 | 0.807 |
| v8 | 0.768 | 0.609 | 0.827 | 0.853 | 0.800 |
| **v8, fresh 50 (post-freeze)** | **0.658** | **0.584** | **0.860** | **0.840** | **0.560** |

## Full run (v8)

- Extraction rules unchanged from the v8 freeze (`RULES_FROZEN_v8.txt`).
- `run_pipeline_v8.py` and `job_family_classifier.load_model()` no longer retrain the job-family
  model; they only load the frozen `cleaned/job_family_tfidf_lr_v8.joblib` (a test checks its
  SHA-256 is unchanged before and after a run).
- Occupation grouping moved from the predicted `job_family` to LinkedIn's `search_position`
  (1,993 values → 12 groups + Other, `config/search_position_groups.csv`). `job_family_pred` is
  still written but is experimental (~0.6 accuracy) and not used in the analysis.
- `run_full_v8.py`: chunked, resumable run over all 1,348,454 postings
  (`outputs/full_v8/run_state.json`, ~35 postings/s, ~6 GB peak memory).
- Summary tables, EDA, models and the dashboard are built by `src/analysis/` and `app/`.

## v8 — general fixes found on the holdout, then freeze (2026-10-13)

- Skill rules untouched (still the v7 freeze).
- Education: `MS Office / Word / Excel / Project / Teams` and bare `master` (master data, scrum
  master) no longer count as a master's degree.
- Experience: word numbers and bracketed forms (`Five (5) to ten (10) years`, `two years`,
  `5+ years in relevant position`).
- Certificates: more dictionary entries (CIPD, LMFT, LPC, LCSW, RDCS, RCS, veterinary and teaching
  licences); "under the supervision of an RN" is not a requirement for the role.
- Job family: regex rules replaced by TF-IDF (1–2 gram) + logistic regression on title + first 300
  words, trained on the 150 tune labels (5-fold CV 0.69). On fresh postings it reaches only 0.62,
  so it is not used downstream.

## v7 — last tuning round, skill rules frozen (2026-10-13)

- Recall: responsibilities sections treated like requirements; short postings without headers
  treated as requirements; multi-word duty phrases (documentation, reporting, driving, safety) kept.
- Precision: `Recruitment` only in a hiring-function context; figurative "driving results"
  excluded; company-name filter no longer triggered by the job title.
- More certificate entries (309A, CHRP/CHRL, EMR, ARRT, GPhC, ACCA, AAT, …).

## v6 — tuned against the labelled tune set

- Text normalisation (curly quotes), driving licences / CDL classes, `yrs` / `1-year` / PQE forms.
- Education: plural cues, ADN / associate-or-baccalaureate ladders.
- Company-name and boilerplate ("our values") filters; high-false-positive skills only from
  requirements / preferred sections.

## v5 — tighter semantics and two-tier quality checks

- Education cues judged per degree and per sentence; preferred vs required conflicts flagged.
- Experience: overall years left empty when only skill-specific years are stated; company history
  ("over 100 years…") excluded.
- Context filters use the raw skill name with a ±8-word window; case-sensitive short aliases
  (Excel, Git, CSS, CRM, SAP).
- `dup_group_id` = hash of the full description, so chain-store templates can be counted once.
- Blocking checks stop the run before any output is written; tune/holdout split isolated by
  `dup_group_id`.

## v4 — data source and evidence fixes

- Extraction reads the combined all-country file; `text_status` records missing descriptions.
- Every skill row carries an `evidence_id`; merged or absorbed rows are logged, never silently dropped.
- Section headers recognised only at line/bullet start; short aliases matched on word boundaries;
  ambiguous skills only from requirements / preferred / responsibilities sections.
- Two counting modes (`eda_counts_v4.py`): every posting vs one per description template.

## v3 — evidence-bound extraction

- Typed sections of the job description; skills only from relevant sections.
- Evidence (source field, section, matched text, snippet) bound at match time.
- Alias merge → sense disambiguation → hierarchy, in that order; compound skills preserved.
