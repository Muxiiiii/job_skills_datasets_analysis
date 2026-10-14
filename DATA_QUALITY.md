# Data quality notes (caveats for the full-run analysis)

Source: `cleaned/final_eval_v8.md` (fresh 50 previously unseen postings, 2026-10-13).

## Usable fields

| Field | fresh50 metric | How to use it |
|---|---|---|
| Education requirement `edu_required` | accuracy **0.86** | Usable |
| Years of experience `yoe_min_overall` | accuracy **0.84** | Usable; many values are empty, but most extracted values are correct |
| Skills | precision **0.66**, recall **0.58** | **Suitable for frequency rankings and cross-group comparisons**; not suitable as a complete skill list for a single posting |
| Skills (subset where both sources agree) | precision **0.93** | High-confidence view (`high_confidence=true`) |
| Certifications | exact-set match 0.56 (not usable) | **Use only the occurrence rate of individual certifications** (RN, BLS, CDL, Driver's License, etc.) |
| `job_family_pred` | 0.62 | **Not usable / experimental**; for the main grouping use `search_position` → `position_group` |

## Analysis defaults

- Deduplication: each `dup_group_id` is counted once, via `is_dup_primary`; a separate "with duplicates" comparison table is also saved.
- Default skill view: excludes `is_generic` labels and labels whose name contains `(unspecified)`.
- Main grouping dimensions: `position_group` (mapped from LinkedIn `search_position`), `search_country`, `job_level`, `job_type`.

## Numbers not to quote externally

- job_family 0.90 on the tune set (training-set memorization; not valid).
- Certification "exact-set match" accuracy.
- The skill list treated as a gold-standard list for each JD.
