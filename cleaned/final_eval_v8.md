# v8 final validation — frozen v8 pipeline (fresh 50 + holdout 50)

Date: 2026-10-13. Labeling and judgments: Claude (LLM), reading the original JD text of each posting. Rules, code, model and existing outputs were not modified (frozen files have the same SHA-256 before and after); this pass only created new files.

## Conclusions

| Module | fresh50 (clean numbers) | Usable for the full-run analysis? |
|---|---|---|
| Skill extraction | precision 0.658, recall 0.584 | **Usable, with caveats stated.** Suitable for skill frequency rankings and cross-group comparisons; not suitable as an accurate skill list for a single posting. The subset where both sources agree (job_skills + body text) has precision 0.93 and can serve as a high-confidence view. |
| job_family | **0.62** (95% interval 0.48–0.74) | **Not usable; below 0.70.** It is 0.54 on the holdout, exactly the same as v7. See "Anomaly 1" below: the v8 classifier is effectively not in use. |
| edu_required | 0.86 (0.74–0.93) | Usable. |
| yoe_overall | 0.84 (0.71–0.92) | Usable. The main problem is missed extractions (many empty values); most extracted values are correct. |
| certs_required | in-dictionary 0.72, including out-of-dictionary 0.56 | **Not usable under the "exact-set match" definition.** Only suitable for the occurrence rate of individual major certifications (RN, BLS, CDL, Driver's License); do not use `certifications_pipe` as a "required certifications" list, because it mixes in preferred certifications. |

Skills, edu and yoe on fresh50 are all within the interval of the holdout figures, with no new sign of overfitting. job_family and certs are the two fields that cannot be used directly.

## Side-by-side comparison

| Metric | tune v8 (n=150) | holdout v7 | holdout v8 | **fresh50 v8** | fresh50 95% interval |
|---|---|---|---|---|---|
| Skill precision | 0.768 (1001/1303)ᵃ | 0.724 (427/590) | 0.724 (427/590) | **0.658** (302/459) | 0.60–0.71ᵇ |
| Skill recall (in-vocabulary, strict) | 0.609 (224/368)ᶜ | 0.578 (337/583) | 0.578 (337/583) | **0.584** (230/394) | 0.52–0.64ᵇ |
| Skill recall (including out-of-dictionary) | — | 0.439 (337/768) | 0.439 | 0.429 (230/536) | — |
| job_family (strict) | 0.900 (135/150)ᵈ | 0.540 (27/50) | **0.540** (27/50) | **0.620** (31/50) | 0.48–0.74 |
| job_family (alt accepted) | 0.913 | 0.560 | 0.560 | 0.660 (33/50) | 0.52–0.78 |
| edu_required | 0.827 (124/150) | 0.760 (38/50) | 0.820 (41/50) | **0.860** (43/50) | 0.74–0.93 |
| yoe_overall | 0.853 (128/150) | 0.700 (35/50) | 0.880 (44/50) | **0.840** (42/50) | 0.71–0.92 |
| certs_required (including out-of-dictionary) | 0.800 (120/150) | 0.720 (36/50) | 0.760 (38/50) | **0.560** (28/50) | 0.42–0.69 |
| certs_required (in-dictionary) | 0.860 (129/150) | 0.840 (42/50)ᵉ | 0.840 (42/50) | **0.720** (36/50) | 0.58–0.83 |
| edu_preferred | 0.947 | 0.940 | 0.940 | 0.960 | — |

95% intervals for holdout v8 (n=50, Wilson): family 0.40–0.67, edu 0.69–0.90, yoe 0.76–0.94, certs including out-of-dictionary 0.63–0.86, in-dictionary 0.71–0.92; precision 0.67–0.77, recall 0.52–0.63.

- ᵃ Tune precision covers only the 1303 predictions judged at v5; another 401 predictions added from v6 onward have no labels, so the number is optimistic.
- ᵇ Intervals for precision / recall are bootstrapped by posting (skills within a posting are not independent); the rest are Wilson intervals.
- ᶜ Tune recall uses only the 30 full_recall postings.
- ᵈ An in-training-set number; it cannot be used as a quality metric (see Anomaly 1).
- ᵉ `holdout_eval_v7.md` reports 0.900. The difference comes from the dictionary: v8 added CIPD, LMFT, Veterinary License and others to `CERT_DICT`, so these gold certifications now count as "in-dictionary", and the v7 predictions missed them. Recomputed with the v8 dictionary it is 0.840.

**The v7→v8 gains on the holdout are for reference only**: the edu (+0.06), yoe (+0.18) and certs (+0.04) patches were designed after looking at the holdout errors. fresh50 is the only sample these patches have not seen, so it is the reference: edu 0.86 and yoe 0.84 show the patches generalize; certs did not improve along with them.

## Sample and procedure

- **Sampling**: `cleaned/jobs_combined.parquet` (the same source as the v5 sample, four countries), keeping only postings with JD text (1,297,332), randomly permuted with `numpy.default_rng(20261013)` and taking the first 50 in order. The exclusion set was drawn broadly: all 5,000 postings in `sample_links_v5.csv` (which include tune 150 + holdout 50) plus any posting sharing a `dup_group_id` with them; dup groups are also not repeated within fresh. 2 candidates were skipped. Country distribution: US 43, UK 4, CA 2, AU 1.
- **Blind labeling**: the gold was written first from reading only the 50 JDs, and the SHA-256 of `cleaned/fresh50_gold_claude.csv` was recorded in `cleaned/fresh50_gold_claude.sha256` (`58df6c90…94bd2`); only then was the pipeline run and the predictions read. The gold was not edited afterwards, and the hash was verified to match at the end. Scripts were used only to display text, write files, check whether skill names are in the vocabulary, and count.
- **Pipeline**: a newly written script calls the same set of functions from `run_pipeline_v8.py` step by step and loads the frozen `job_family_tfidf_lr_v8.joblib` without retraining. It was first verified on the holdout 50: the 590 skill rows, family, edu, yoe and certs match the existing `*_v8_sample5000` outputs row for row; it was then applied to fresh50.
- **Scoring**: calls `_norm_edu`, `_yoe_eq`, `_certs_*` and related functions from `scripts/eval_tune_v6.py` directly, with the same definitions as tune / holdout.

New files: `fresh50_links_v8.csv`, `fresh50_gold_claude.csv`, `fresh50_gold_claude.sha256`, `job_skill_refined_v8_fresh50.csv`, `job_features_v8_fresh50.csv`, `fresh50_skill_judgments_claude.csv`, `final_eval_v8.md` (all in `cleaned/`).

## Anomalies

1. **The v8 job_family classifier is essentially not in use.** `predict_job_family` falls back to the old regex rules when the top probability is below `min_proba=0.18`. The model has 31 classes and was trained on only 150 rows; the median top probability is just 0.05:
   - Of the 5,000 postings, 4,907 (98%) fall back to the rules; only 93 use the classifier, and 49 of those are the tune training samples themselves.
   - All 50 holdout postings fall back, and the predictions are identical to v7 posting by posting, so holdout family is still 0.54. Only 1 posting in fresh50 uses the classifier.
   - The tune 0.900 = 49 training postings memorized by the model (49/49) + 101 postings that go through the rules (86/101 = 0.85). The gain from 0.827 to 0.900 comes entirely from training-set memorization.
   - Removing the threshold and using only the classifier (diagnostic only, not the frozen pipeline): holdout 0.44 (22/50), fresh50 0.50 (25/50), worse than the rules. So lowering the threshold does not solve the problem; 150 labels are not enough for 31 classes.
2. **`main()` in `run_pipeline_v8.py` calls `train_and_save()` on every run, retraining and overwriting the frozen joblib.** This validation did not take that path. If the full run uses `main()` directly, the frozen model file will be rewritten.
3. **The tune/holdout split in `validation_sample_v8.csv` differs from v5** (the split is stratified by job_family; the family predictions changed, so the split changed). `validation_tune_links_v8.csv` / `validation_holdout_links_v8.csv` are not the real tune / holdout sets; do not use them. The real split is in `validation_sample_v5.csv` and the gold files.
4. **Leakage check passed**: the classifier reads only the 150 rows with `split == 'tune'` in `gold_annotation_template_v5_claude.csv`; `job_family_gold` is empty for all 50 holdout rows in that file; the tune set matches the v5 split; fresh50 has no overlap with the 5,000-posting sample or with the gold file. Classifier training used no holdout or fresh labels.
5. Skill precision on fresh50 (0.658) is 0.066 lower than on the holdout (0.724). The two intervals overlap (0.60–0.71 vs 0.67–0.77), and fresh has more false positives from company descriptions (see below). Precision on the full data is more likely between 0.65 and 0.72 than the tune figure of 0.77.

## fresh50: job_family (31/50)

The 5 most-confused pairs (predicted → gold):

| Predicted | gold | Count | Postings |
|---|---|---|---|
| Other | Sales | 2 | Client Advisor (VinFast), State Farm Agent Team Member |
| Other | Construction & Trades | 2 | Security Systems Installation Technician, Starlight Homes Internship |
| Management General | Finance & Accounting | 2 | Large Account Business Segment Manager (insurance underwriting), Senior Manager, Development Advisory (Baker Tilly) |
| Nursing & Clinical | Personal Care / Physician & PA | 1 each | CNA home care aide, Surgical Oncology NP/PA |
| Allied Health / Behavioral Health | Imaging & Radiology / Allied Health | 1 each | Radiology Technologist, Psychiatric Occupational Therapist |

Only the first three pairs occur twice; the other 13 errors are all different. It is clearer by predicted class:

- All 9 postings predicted as `Other` are wrong (on the holdout, all 10 were wrong). Besides the 4 above: Team Leader - Children, Master Resilience Trainer, Space Management Specialist, Cleanroom Technician, and the French-language Concepteur Surfacique.
- `Management General`: 2 of 3 postings wrong.
- Clear rule errors: `Substitute Drivers` (school bus drivers) → Project / Product Mgmt; `Temporary Park Planner` → Supply Chain & Ops; `Data Center Engineer` → Engineering (Non-software).
- In my gold, I marked 5 postings as "uncertain" myself (the internship, the insurance underwriting manager, the Resilience Trainer, a BIM engineer, the advisory senior manager). With every alt accepted the figure is 0.66, still below 0.70.

## fresh50: skills

**precision 0.658 (302/459)**

| Slice | precision |
|---|---|
| Both sources agree (job_skills\|summary) | 0.926 (113/122) |
| job_skills only (ner_only) | 0.607 (54/89) |
| summary only | 0.544 (135/248) |
| Per-posting mean / median | 0.607 / 0.634 (12 postings below 0.5) |

Sensitivity: 86 judgments carry a borderline note (51 judged 1, 35 judged 0); flipping them all one way puts precision between 0.547 and 0.734.

False-positive types (157 rows):

| error_type | Count | Share | Typical examples |
|---|---|---|---|
| wrong_sense | 37 | 24% | "driving force" / "driving up memberships" → Driving; "teaching hospital" → Teaching; "creative arts programming" → Software Development; CSS (a spirits certification) → CSS; organization meaning the company |
| company_title | 36 | 23% | Agency and company descriptions, lists of core values, a university's list of colleges (Engineering, Computer Science, Business Administration) |
| ner_unsupported | 32 | 20% | Present in job_skills with no support in the body text (Problem Solving, Decision Making, Dental, Budgeting) |
| not_requirement | 26 | 17% | EEO clauses, "No surgery or dentistry required", optional degree majors, "We are interviewing candidates" → Recruitment |
| too_generic | 12 | 8% | Management (unspecified) from "records management", "wound management", "learning management system" |
| benefit | 8 | 5% | mentorship, career development, flexibility |
| wrong_alias | 6 | 4% | installation → Repair (3 times); product knowledge → Merchandising |

Compared with the holdout, the share of company_title doubled (11% → 23%); the fresh sample has more agency postings and JDs with long company introductions. The `(unspecified)` labels total 44 rows, 15 correct; of these, Management (unspecified) is 2/17.

**recall 0.584 (230/394)**. Most missed: Communication 9, Documentation 8, Patient Care 6, Client Relationships 4, Medication Administration 4, Customer Service 4, Care Planning 4, Organization 4, Multitasking 4, Analysis (unspecified) 4, Driving 4, People Management 4. These are still mostly expressed as duty sentences. Postings with near-zero recall: Psychiatric Occupational Therapist (0/5), Attending Physician (1/7), State Farm Agent Team Member (2/11), CNA (2/9). For the French JD, skills in the body text were matched only through the job_skills field.

## fresh50: qualification fields

**edu_required (7 errors)**

- 5 missed: `Four-year Bachelor's Degree in Electrical Engineering`, `H.S. Diploma or equivalent required`, `DVM/VMD degree`, `Medical doctor`, `Master's or Doctoral degree` (tagged as mentioned rather than required).
- 1 spurious master: `MS/PCU RN` (MS means Med-Surg) is still classified as master. The v8 MS patch does not cover this form, which is common in travel-nurse postings.
- 1 wrong level: the body text says `Master's degree`, but "doctoral university" in the company introduction was taken as phd.

**yoe_overall (8 errors)**: 6 missed, 2 wrong values.

- Missed: `1< year of relevant HR experience preferred`, `three to six months related experience`, `6 months current L&D experience required`, `2+ Years post Part 3 qualification`, `A minimum of five (5) plus years of progressive related consulting experience`, French `5 à 10 ans`.
- Wrong value: `8-10 years commercial lines experience` was extracted as the 5 from a later preferred sub-item; `Required exp: 1/year` was extracted as the preferred 2.
- Months and French are outside the scope of the rules; `five (5) plus years` is a pattern v8 should cover.

**certs_required (22 errors including out-of-dictionary, 14 of them in-dictionary)**

- Preferred certifications mixed into the predictions (4 postings): SHRM/PHR, CCNA and CPA are all explicitly preferred. `certifications_pipe` does not distinguish required from preferred, while the gold records only required.
- False positives from company descriptions or negations (5 postings): a job-site description → PA; "CPA firm" → CPA; "board-certified doctors" → Board Certification; `Board Certification Required: No` → Board Certification; `BLS or as required per unit (ACLS, PALS…)` → ACLS, PALS.
- Missed in-dictionary certifications (4 postings): `Active bar membership in California` (Bar Admission), `Active license in good standing to practice` (Veterinary License), `Registered to practice medicine` (Medical License), `BCLS` (a spelling of BLS).
- Out-of-dictionary certifications (8 postings wrong for this reason alone): CDL S/P endorsements, DMV Salesperson License, RIBA Part 3, CTS, insurance sales license, PRINCE2/APM, OT License, program-internal certifications.
- The way the gold is written also matters: I wrote "either/or" as `CNA/HHA` and `BLS/ACLS`, and the script scores them wrong because it compares the whole string. Splitting the either/or items and allowing gold preferred certifications to appear in the predictions, in-dictionary accuracy is 0.82 (41/50) on fresh50 and 0.90 (45/50) on holdout v8. So part of the 0.72 is a matter of definition, but the false positives and misses are real.

## Data observations

- 8 of the 50 postings are short posts with almost no requirements content (job-site redirect posts, travel-nurse templates, a benefits-only veterinary ad); skill and qualification fields are naturally empty for these.
- 1 French JD (Creaform, Quebec). The pipeline supports English only; Canadian postings in the full data will have similar cases.
- Title and body mismatches: a posting titled `Lecturer` whose body is a counseling practicum supervisor; a posting titled `Senior Compliance Manager` whose body is a consulting senior manager.

## Notes on definitions

- The gold conventions follow `llm_labeling_v5_notes.md` and the holdout: skills are judged by "does the role require it" rather than by evidence snippet; yoe takes the lowest overall figure, with preferred also counted; a degree major counts as a skill only when it is the discipline of the role itself; out-of-dictionary certifications such as driver's licenses and medical licenses are recorded as usual.
- The gold and judgments are single-annotator LLM labels with no human review. The 19 family disagreements and the 86 borderline judgments are worth a manual spot check.
- At n=50, the interval for a single metric is about ±0.12–0.14. Differences of around 0.05 between fresh50 and the holdout are all within noise; the two conclusions that family is below 0.70 and certs is below 0.80 are not affected by noise (the upper bound of the family interval, 0.74, is slightly over the line, but the independent holdout result is 0.54, and pooling the two samples gives 58/100 = 0.58, interval 0.48–0.67).
