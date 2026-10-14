# Holdout final validation — frozen v7 pipeline (50 postings)

Date: 2026-10-13. Labeling and judgments: Claude (LLM), reading `summary_full` for each posting. Rules, code and existing outputs were not modified; this pass only created 3 new files:

| File | Contents |
|---|---|
| `cleaned/holdout_gold_claude.csv` | Blind-labeled gold for 50 postings (family, all skills, edu, yoe, certs, notes) |
| `cleaned/holdout_skill_judgments_claude.csv` | Row-by-row judgments of v7's 590 predicted skills for these 50 postings (correct 1/0 + error_type) |
| `cleaned/holdout_eval_v7.md` | This report |

## Conclusions

**There is overfitting, but it is concentrated in job_family; skill extraction largely generalizes.**

- **job_family is severely overfit**: tune 0.827 → holdout 0.540 (gap 0.287). On the same holdout postings v5 scores 0.52 and v7 scores 0.54, i.e. the v6/v7 family rule changes brought almost no benefit outside tune.
- **yoe_overall (gap 0.107) and certs_required including out-of-dictionary (gap 0.087) exceed 0.05** and miss the 0.80 target.
- **Skill precision (gap 0.044), recall (gap 0.031) and edu_required (gap 0.047) are within 0.05**, but all are below tune, and edu sits right at the threshold.
- The v6→v7 recall gain is real on the holdout (0.513 → 0.578), not something that only works on tune.

## Comparison table

| Metric | tune v7 | holdout v7 | Gap (tune − holdout) | ≤0.05? | Target | Holdout meets target? |
|---|---|---|---|---|---|---|
| Skill precision | 0.768 (1001/1303) | **0.724** (427/590) | 0.044 | Yes | ≥0.82 | No |
| Skill recall (in-vocabulary, strict) | 0.609 (224/368) | **0.578** (337/583) | 0.031 | Yes | ≥0.60 | No |
| job_family (strict) | 0.827 (124/150) | **0.540** (27/50) | **0.287** | **No** | ≥0.75 | No |
| edu_required | 0.807 (121/150) | **0.760** (38/50) | 0.047 | Yes (borderline) | ≥0.80 | No |
| yoe_overall | 0.807 (121/150) | **0.700** (35/50) | **0.107** | **No** | ≥0.80 | No |
| certs_required (including out-of-dictionary) | 0.807 (121/150) | **0.720** (36/50) | **0.087** | **No** | ≥0.80 | No |
| certs_required (in-dictionary) | 0.873 | 0.900 | −0.027 | Yes | — | — |
| edu_preferred | 0.940 | 0.940 | 0.000 | Yes | — | — |
| job_family (lenient, alt accepted) | 0.840 | 0.560 | 0.280 | No | — | — |

Performance of each version on the same holdout postings (scored against the same holdout gold; precision was judged only for the v7 predictions):

| Version | Predictions | recall | job_family | edu_required | yoe_overall | certs (all) | certs (in-dictionary) |
|---|---|---|---|---|---|---|---|
| v5 | 522 | 0.509 | 0.52 | 0.50 | 0.54 | 0.66 | 0.84 |
| v6 | 473 | 0.513 | 0.54 | 0.76 | 0.70 | 0.72 | 0.90 |
| v7 | 590 | 0.578 | 0.54 | 0.76 | 0.70 | 0.72 | 0.90 |

Most of the gains in edu, yoe and certs relative to v5 carry over to the holdout, only smaller than on tune; family does not carry over.

## Notes on definitions and comparability

- The computation calls `skill_recall`, `quals_accuracy`, `_norm_edu`, `_yoe_eq` and `_certs_*` from `scripts/eval_tune_v6.py` directly; precision and family are computed with the same definitions as that script. Predictions come from the existing `job_skill_refined_v7_sample5000.csv` and `job_features_v7_sample5000.csv` (which already include the holdout, so the pipeline did not need to be re-run).
- **Tune precision of 0.768 may be optimistic**: it is computed only on the 1303 rows judged at v5; the 401 predictions added in v6/v7 have no labels. The holdout 0.724 covers all 590 rows. The fully judged tune precision at v5 was 0.721, almost the same as the holdout. So part of the 0.044 gap comes from the definition rather than from overfitting.
- **The recall posting sets differ**: tune uses the 30 `full_recall` postings (368 in-vocabulary gold skills); the holdout has no `full_recall` flag and uses all 50 postings (583).
- **A small flaw in the evaluation script**: `skill_recall` reads an empty `gold_skills_all` as the string `"nan"` and counts it as 1 miss (the Assistant General Manager posting with no JD text). The script's raw output is 337/584 = 0.577; the table above uses 337/583 = 0.578 with that row removed.
- **Sample size**: posting-level metrics have n=50, and the 95% interval for a single metric is about ±0.13, so the 0.05 threshold is within noise for edu/yoe/certs. The family gap (0.287) is far beyond noise.
- Blind-labeling order: the gold was written first from reading the 50 JDs (the file hash was recorded once it was written), and only then were the predictions read. The gold was not edited afterwards. The only posting whose title was read is the one with no JD text.

## Skill precision breakdown

| Slice | holdout precision |
|---|---|
| sources = job_skills\|summary (both sources agree) | 0.918 (134/146) |
| sources = job_skills (ner_only) | 0.735 (83/113) |
| sources = summary only | 0.634 (210/331) |
| Per-posting mean / median | 0.691 / 0.727 (5 postings below 0.5) |

Sensitivity: 35 judgments carry a borderline note (21 judged 1, 14 judged 0); flipping them all one way puts precision between 0.688 and 0.747.

### Error types (163 false positives)

| Rank | error_type | Count | Share | Typical examples |
|---|---|---|---|---|
| 1 | wrong_sense | 48 | 29% | "driving the commercial success" → Driving; "eye-hand coordination" → Project Coordination; "electrical shock" → Electrical Systems; "organization" (meaning the institution) → Organization |
| 2 | not_requirement | 32 | 20% | EEO / Clery safety report / recruiting contact details; one of several optional degree majors; "no management responsibilities" → People Management |
| 3 | ner_unsupported | 28 | 17% | Present in job_skills with no support in the JD body (Attention to Detail, Budgeting, Forecasting, Dental) |
| 4 | too_generic | 21 | 13% | Development / Management / Quality / Operations (unspecified) as fragments of other phrases |
| 5 | company_title | 18 | 11% | Company descriptions, agency descriptions, words that appear only in the job title |
| 6 | wrong_alias | 9 | 6% | installation → Repair; product knowledge → Merchandising; Rehabilitation → Physical Therapy |
| 7 | benefit | 7 | 4% | "flexible scheduling", "professional development reimbursement" |

The ordering is broadly consistent with tune v7 (tune: wrong_sense 84, not_requirement 67, ner_unsupported 62, company_title 42, benefit 26, wrong_alias 12, too_generic 9). The difference is that too_generic has a clearly higher share on the holdout.

### Worst skills (≥5 rows)

| Skill | precision | Main cause |
|---|---|---|
| Development (unspecified) | 1/11 | "development of X" fragments, R&D, benefits |
| Human Resources | 1/7 | HR department / contact person |
| Quality (unspecified) | 1/6 | "quality metrics / quality care" fragments |
| Organization | 2/10 | Means "institution" rather than organizational skills |
| Production | 1/5 | Company business, "production-ready" |
| Quality Assurance | 1/5 | ner_only with no support in the body text |
| Management (unspecified) | 4/19 | Refers to management as a group; "X management" fragments |
| Engineering | 2/7 | Degree-major fragments, department names |
| Operations (unspecified) | 2/7 | Department names, job titles |
| Training (unspecified) | 5/10 | EEO statements, training the candidate receives |
| Scheduling | 4/8 | "scheduling an interview", flexible-schedule benefits |

The four labels Development / Management / Quality / Operations (unspecified) total 43 rows with only 8 correct, contributing 35 of the 163 false positives.

## Skill recall

- In-vocabulary, strict: 0.578 (337/583). Relaxed by the near-synonym names I flagged in the notes (Computer Literacy/Proficiency, Quality Assurance/Quality Control (Manufacturing), Employee Training / L&D vs Training (unspecified), Writing/Written Communication, etc.), it is 0.621 (362/583).
- Including out-of-dictionary: the gold has a further 185 OOV skills; counting all of them, recall is 0.439 (337/768).
- Most missed: Teamwork 8, Written Communication 7, People Management 7, Employee Training / L&D 7, Coaching 6, Documentation 6, Organization 6, Contract Administration 5, Interpersonal Skills 5, Compliance 5. Most are still expressed as duty sentences ("supervise staff", "train, coach and develop employees", "maintains accurate records").
- 3 postings with near-zero output: Registered Nurse (IntelyCare; 12 in-vocabulary gold skills, 1 hit), Associate Veterinarian (1 hit), Kitchen Supervisor (only the 6 ner_only rows).

## job_family (27/50)

- 10 postings are predicted as `Other`, all wrong; 7 are predicted as `Management General`, of which I also labeled only 2 as Management General. These two classes together account for 15 errors, 65% of the 23 errors.
- Main confusions (predicted → gold): Other → Construction & Trades 3 (Regional Technician, Quantity Surveyor, Reliability Technician); Management General → Construction & Trades 2 (Contracts Manager Ducting, Design Manager); Management General → Finance & Accounting 2 (Client Service Manager, Tax Manager); Other → Behavioral Health 2 (LMFT, Team Leader); Other → Education 2 (PT Faculty, Special Education Instructional Coach).
- Clear rule gaps: `AWS Solution Architect` → Architecture & Design; `Senior Manager, Machine Learning Engineering` → Engineering (Non-software); `Molecular Immunologist`, `LMFT`, `Land Surveyor` → Other.
- 4–5 of my gold labels are debatable (the assignment of Senior Operations Strategy Analyst, Senior Engineering Project Manager, Lead Cardiac Sonographer and Occupational Therapist; putting technicians under Construction & Trades follows the tune precedent). Even conceding all of them to the pipeline gives only about 0.62–0.64; the conclusion does not change.

## Qualification field error details

**edu_required (12 errors)**

- **6 are spurious `master`**: matches on "MS Office / MS Word / MS Project" (treated as an M.S. degree) and the ordinary word "master" ("master contract agreement", "Supply Chain master data", "master sanitation schedule", "Master Level Business Systems Analyst"). Affected: Procurement Coordinator, Supply Chain PTM, Lead Security Engineer, Quality Supervisor, Reliability Technician, Territory Sales Manager. This is the same class of problem as "as" → associate at v5, and it did not surface on tune.
- 3 missed: HNC (Contracts Manager), "BSc in Quantity Surveying", DVM.
- 3 ladder/level differences: Design Manager "HNC or Degree" (predicted bachelor, gold associate); BI Developer degree ladder (predicted associate, gold takes the first rung, bachelor); the Customer Service Rep high-school requirement sits under "Great if you have" but was classified as required.

**yoe_overall (15 errors)**: 13 are missed, 2 are wrong values.

- The misses include clearly simple patterns: spelled-out numbers with parentheses, "Five (5) to ten (10) years", "Three (3) – five (5) years", "Minimum of three (3) or more years"; "Two years prior experience of…", "Two years of supervisor experience", "5+ years in relevant position", "Minimum of one year of experience as a Cardiac Sonographer (Required)".
- Wrong values: Senior Engineering PM (predicted 3, gold 7), ML Engineering Sr Manager (predicted 2, gold 8) — both took the smallest sub-item figure in a list instead of the overall figure.
- About 5 of the gold values are debatable ("4 months" recorded as 0.33, preferred years, Pattern I/II, a degree ladder, 2 years injection molding / 3 years manufacturing).

**certs_required (14 errors, 9 of them solely due to out-of-dictionary certifications)**

- Out-of-dictionary: APICS BSCM, CIPD, Veterinary License, DCWF + IAM/IAT II, NIHSS, RDCS/RCS, LMFT, OT License, Illinois PEL, First Aid, PLS.
- 5 genuine in-dictionary errors: Nursing Technician has extra RN, LPN ("under the supervision of an RN or LPN"); PPG RN has extra LPN (a benefits sentence) and ACLS (preferred); Lead Security Engineer has extra PMP (an alternative to the degree); Occupational Therapist has extra Driver's License ("if required by the position"); Land Surveyor's PLS/PMP either/or.

## Recommendations (rules are frozen; the following wait until they are unfrozen)

1. job_family is the only module that is definitely overfit. It should be the first thing reworked after unfreezing, and validated on a new unseen sample rather than tuned further against tune. For now, any conclusion in the full-run analysis that groups by family is unreliable (about half of holdout postings are misassigned, and `Other` is entirely wrong).
2. The "MS / master" mismatches in edu, the "Five (5) years" pattern in yoe, and the four (unspecified) labels are all clustered errors that rules can fix.
3. Before the full run, reports should use the holdout numbers (precision 0.72, recall 0.58, family 0.54, edu 0.76, yoe 0.70, certs 0.72) as the externally quoted quality figures, not the tune numbers.
4. My gold and judgments are single-annotator LLM labels; a manual spot check of the 23 family disagreements and the 35 borderline judgments is recommended.
