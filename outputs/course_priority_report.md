# Course priority: a composite ranking of skills for curriculum planning

Source: `outputs/full_v8/chunks (6 file(s))` — 259,589 deduplicated postings, 278 specific skills with ≥ 100 postings. Generated 2026-10-14T10:44:40+00:00.

Reproduce with `python -m src.analysis.course_priority` (pilot) or `--preset full`. Tables are in `outputs/summary/pilot/course_priority/`.

## Method

**Unit and filters.** One posting per `dup_group_id`; generic and `(unspecified)` labels excluded; a skill needs ≥ 100 postings (same eligibility as the co-occurrence network in the curriculum analysis).

**Dimensions** (all oriented so that larger = higher priority):

| Dimension | Definition | Why it matters for a course |
|---|---|---|
| Demand | Share of deduplicated postings that mention the skill. | How many jobs the course serves. |
| Breadth | Number of the 12 occupation groups (`Other` excluded) where the skill's RCA > 1 with ≥ 20 postings in the group. | Transferability across fields. |
| Centrality | Weighted degree (sum of PMI edge weights) in the co-occurrence network: edge if lift > 1.5 and ≥ 30 co-occurring postings. PageRank is kept as an alternative (Spearman with weighted degree 0.98). | Skills that connect to many others anchor a bundle (Alabdulkareem et al. 2018). PMI is prevalence-adjusted, so very common skills score low here by construction (a skill in a share *s* of postings has lift ≤ 1/*s*); prevalence is carried by demand. |
| Accessibility (optional) | Reverse-scored mean of (a) median minimum years of experience among postings with the skill that state YOE and (b) share asking for a bachelor's degree or higher among postings with the skill that state a degree. | Entry-level reach; it is a learner-side judgement, so it is reported with and without. |

**Scaling.** Min-max to [0, 1] per dimension; composite = weighted mean of the scaled dimensions.

**Weights** (OECD & JRC 2008, ch. 6–7; Saisana, Saltelli & Tarantola 2005):

- *Equal weights* — the headline ranking.
- *Method A, Monte Carlo* — 2,000 weight vectors from a flat Dirichlet(α = 1) (uniform over all weightings that sum to 1; seed 42). Each draw gives a ranking; we report the median rank, the 5–95 % rank interval and the probability of landing in the top 10 / top 20.
- *Method B, data-driven* — entropy weights (more weight to dimensions that separate skills more sharply) and CRITIC weights (Diakoulaki et al. 1995: standard deviation × conflict with the other dimensions).
- *Agreement* — Kendall tau-b and top-10 intersection between the equal-weight, Monte Carlo median, entropy and CRITIC rankings.
- *Robustness* — everything is repeated without accessibility ("3d").

Weights used:

| Variant | Method | demand | breadth | centrality | accessibility |
|---|---|---|---|---|---|
| 3d | critic | 0.198 | 0.377 | 0.425 | – |
| 3d | entropy | 0.735 | 0.168 | 0.097 | – |
| 3d | equal | 0.333 | 0.333 | 0.333 | – |
| 4d | critic | 0.130 | 0.256 | 0.310 | 0.304 |
| 4d | entropy | 0.631 | 0.144 | 0.083 | 0.141 |
| 4d | equal | 0.250 | 0.250 | 0.250 | 0.250 |

Spearman correlation between the raw dimensions (high values mean two dimensions largely double-count):

| | demand | breadth | centrality | accessibility |
|---|---|---|---|---|
| demand | 1.00 | 0.42 | 0.03 | 0.15 |
| breadth | 0.42 | 1.00 | 0.09 | 0.11 |
| centrality | 0.03 | 0.09 | 1.00 | -0.34 |
| accessibility | 0.15 | 0.11 | -0.34 | 1.00 |

## Results (four dimensions)

| Equal-weight rank | Skill | Score | MC median rank | MC 5–95 % | P(top 10) | P(top 20) | Entropy rank | CRITIC rank |
|---|---|---|---|---|---|---|---|---|
| 1 | Teamwork | 0.560 | 3 | 1–224 | 0.61 | 0.67 | 2 | 20 |
| 2 | Attention to Detail | 0.515 | 7 | 2–152 | 0.57 | 0.66 | 5 | 13 |
| 3 | Mathematical Calculations | 0.507 | 12 | 2–47 | 0.46 | 0.72 | 28 | 1 |
| 4 | Goal Setting | 0.501 | 14 | 1–110 | 0.44 | 0.59 | 34 | 3 |
| 5 | Workplace / OSHA Safety | 0.500 | 12 | 4–94 | 0.47 | 0.65 | 6 | 15 |
| 6 | Automation | 0.493 | 12 | 1–155 | 0.48 | 0.61 | 39 | 4 |
| 7 | Confidentiality | 0.493 | 14 | 5–47 | 0.30 | 0.66 | 23 | 5 |
| 8 | Cash Handling | 0.484 | 25 | 1–103 | 0.37 | 0.47 | 37 | 2 |
| 9 | Conflict Resolution | 0.482 | 20 | 6–40 | 0.17 | 0.51 | 29 | 6 |
| 10 | Creativity | 0.480 | 16 | 3–116 | 0.38 | 0.55 | 12 | 14 |
| 11 | Written Communication | 0.476 | 17 | 4–125 | 0.37 | 0.54 | 10 | 16 |
| 12 | Communication | 0.475 | 36 | 1–256 | 0.39 | 0.44 | 1 | 112 |
| 13 | Delegation | 0.474 | 22 | 7–72 | 0.19 | 0.47 | 43 | 7 |
| 14 | Critical Thinking | 0.473 | 16 | 7–90 | 0.31 | 0.57 | 9 | 18 |
| 15 | Problem Solving | 0.470 | 26 | 3–134 | 0.33 | 0.43 | 3 | 43 |
| 16 | Microsoft PowerPoint | 0.468 | 22 | 8–76 | 0.14 | 0.47 | 33 | 10 |
| 17 | Production | 0.465 | 19 | 10–74 | 0.07 | 0.53 | 14 | 17 |
| 18 | Customer Service | 0.465 | 25 | 3–172 | 0.34 | 0.46 | 4 | 40 |
| 19 | Stocking | 0.459 | 37 | 2–139 | 0.31 | 0.39 | 45 | 8 |
| 20 | Retail Operations | 0.454 | 38 | 2–157 | 0.31 | 0.39 | 38 | 9 |
| 21 | Stress Management | 0.454 | 31 | 10–103 | 0.09 | 0.33 | 46 | 12 |
| 22 | Databases | 0.451 | 27 | 5–109 | 0.17 | 0.38 | 57 | 11 |
| 23 | Data Analysis | 0.442 | 27 | 13–103 | 0.02 | 0.26 | 15 | 29 |
| 24 | Scheduling | 0.442 | 30 | 20–64 | 0.00 | 0.06 | 18 | 24 |
| 25 | Writing | 0.442 | 31 | 14–103 | 0.00 | 0.30 | 21 | 30 |

**Stable top-10 skills** (P(top 10) ≥ 0.8 under random weights): none.

**Stable top-20 skills** (P(top 20) ≥ 0.8): none.

**Scaling sensitivity.** With percentile scaling instead of minmax, the equal-weight ranking has Kendall tau 0.733 with the one above and shares 4/10 of its top 10.

**Agreement between methods (4d):**

| Method A | Method B | Kendall tau | Top-10 overlap |
|---|---|---|---|
| equal | mc_median | 0.946 | 8/10 |
| equal | entropy | 0.761 | 3/10 |
| equal | critic | 0.915 | 6/10 |
| mc_median | entropy | 0.778 | 5/10 |
| mc_median | critic | 0.874 | 4/10 |
| entropy | critic | 0.686 | 0/10 |

**Agreement between methods (3d):**

| Method A | Method B | Kendall tau | Top-10 overlap |
|---|---|---|---|
| equal | mc_median | 0.972 | 9/10 |
| equal | entropy | 0.737 | 6/10 |
| equal | critic | 0.928 | 6/10 |
| mc_median | entropy | 0.752 | 5/10 |
| mc_median | critic | 0.913 | 6/10 |
| entropy | critic | 0.665 | 3/10 |

## Robustness: without accessibility (three dimensions)

Kendall tau between the 4d and 3d equal-weight rankings: 0.616; top-10 overlap 5/10.

| Equal-weight rank | Skill | Score | MC median rank | MC 5–95 % | P(top 10) | P(top 20) | Entropy rank | CRITIC rank |
|---|---|---|---|---|---|---|---|---|
| 1 | Teamwork | 0.623 | 2 | 1–237 | 0.66 | 0.70 | 2 | 11 |
| 2 | Automation | 0.585 | 5 | 1–29 | 0.78 | 0.91 | 25 | 1 |
| 3 | Attention to Detail | 0.549 | 4 | 2–154 | 0.64 | 0.68 | 4 | 10 |
| 4 | Creativity | 0.530 | 8 | 2–71 | 0.56 | 0.70 | 10 | 4 |
| 5 | Critical Thinking | 0.520 | 9 | 6–48 | 0.64 | 0.76 | 9 | 7 |
| 6 | Workplace / OSHA Safety | 0.514 | 9 | 5–101 | 0.52 | 0.64 | 6 | 23 |
| 7 | SQL | 0.513 | 11 | 1–74 | 0.49 | 0.59 | 45 | 2 |
| 8 | Written Communication | 0.504 | 11 | 3–113 | 0.48 | 0.62 | 11 | 12 |
| 9 | Communication | 0.500 | 29 | 1–265 | 0.43 | 0.46 | 1 | 98 |
| 10 | Microsoft PowerPoint | 0.493 | 17 | 7–46 | 0.27 | 0.60 | 30 | 8 |
| 11 | Problem Solving | 0.492 | 23 | 3–125 | 0.38 | 0.48 | 3 | 42 |
| 12 | Computer Science | 0.490 | 17 | 2–77 | 0.44 | 0.53 | 49 | 3 |
| 13 | Production | 0.490 | 14 | 9–60 | 0.27 | 0.65 | 14 | 13 |
| 14 | Databases | 0.484 | 20 | 5–51 | 0.18 | 0.51 | 44 | 6 |
| 15 | Data Analysis | 0.481 | 22 | 11–39 | 0.01 | 0.44 | 15 | 18 |

## By occupation group (four dimensions, equal weights)

Demand and centrality are recomputed inside each group (network over the group's postings, same thresholds; skills with ≥ 20 postings in the group); breadth and accessibility are the corpus-wide values.

| Occupation group | Postings | Top 8 (P(top 10) under random weights) |
|---|---|---|
| Creative Media | 4,204 | Workplace / OSHA Safety (0.98), Teamwork (0.70), Attention to Detail (0.84), Problem Solving (0.73), Manufacturing (0.78), Software Development (0.53), Production (0.50), Quality Assurance (0.41) |
| Education | 13,246 | Attention to Detail (0.93), Teamwork (0.69), Problem Solving (0.79), Critical Thinking (0.74), Workplace / OSHA Safety (0.73), Customer Service (0.64), Data Analysis (0.51), Decision Making (0.44) |
| Finance Accounting | 16,183 | Workplace / OSHA Safety (0.72), Attention to Detail (0.61), Data Analysis (0.55), Teamwork (0.56), Microsoft PowerPoint (0.53), Written Communication (0.45), Customer Service (0.46), Confidentiality (0.30) |
| Healthcare Clinical | 18,420 | Teamwork (0.89), Problem Solving (0.80), Workplace / OSHA Safety (0.92), Communication (0.59), Attention to Detail (0.61), Written Communication (0.60), Critical Thinking (0.59), Assessment (0.57) |
| Healthcare Nursing | 11,065 | Conflict Resolution (0.82), Workplace / OSHA Safety (0.90), Teamwork (0.76), Problem Solving (0.74), Critical Thinking (0.72), Quality Improvement (0.56), Confidentiality (0.73), Attention to Detail (0.52) |
| Hospitality Food | 5,667 | Problem Solving (0.77), Customer Service (0.58), Teamwork (0.59), Merchandising (0.58), Inventory Management (0.70), Retail / Store Operations (0.52), Scheduling (0.50), Coaching (0.49) |
| Legal Compliance | 3,620 | Attention to Detail (0.99), Teamwork (0.85), Problem Solving (0.83), Written Communication (0.83), Critical Thinking (0.85), Time Management (0.82), Communication (0.44), Initiative (0.48) |
| Management HR Admin | 54,741 | Teamwork (0.66), Attention to Detail (0.59), Workplace / OSHA Safety (0.60), Critical Thinking (0.61), Confidentiality (0.41), Written Communication (0.46), Customer Service (0.41), Mathematical Calculations (0.29) |
| Sales Customer | 26,990 | Workplace / OSHA Safety (0.85), Teamwork (0.59), Attention to Detail (0.60), Cash Handling (0.44), Retail Operations (0.43), Customer Service (0.44), Conflict Resolution (0.37), Critical Thinking (0.41) |
| Science Research | 2,807 | Teamwork (0.96), Workplace / OSHA Safety (0.98), Problem Solving (0.85), Attention to Detail (0.86), Data Analysis (0.69), Written Communication (0.59), Communication (0.48), Writing (0.82) |
| Skilled Trades Ops | 26,390 | Teamwork (0.70), Workplace / OSHA Safety (0.68), Attention to Detail (0.59), Customer Service (0.51), Problem Solving (0.50), Communication (0.44), Delegation (0.41), Cash Handling (0.39) |
| Tech Engineering | 19,298 | Teamwork (0.71), Workplace / OSHA Safety (0.75), Attention to Detail (0.68), Software Development (0.58), Written Communication (0.43), Problem Solving (0.40), Critical Thinking (0.36), Communication (0.41) |

## Limitations

- **No growth dimension.** The postings are a single snapshot (early 2024), so the ranking says nothing about rising or declining demand; a trend dimension needs a second period.
- **Extraction noise.** Skill precision ≈ 0.66, recall ≈ 0.58 on 50 unseen postings. Demand and co-occurrence inherit this error; small score differences are not meaningful, so read the rank intervals rather than the point ranks.
- **Choice of weight range.** The flat Dirichlet treats every weighting as equally plausible, including extreme ones (e.g. almost all weight on one dimension). Narrower priors (larger α) would give tighter intervals; the intervals here are therefore deliberately conservative. Entropy and CRITIC weights are properties of this data's spread, not statements about what matters for teaching.
- **Skewed demand.** A handful of skills appear in a large share of postings and most in under 3 %; min-max scaling compresses the long tail of demand, which is why entropy weighting puts most weight on demand. The scaling-sensitivity line above shows how much this matters.
- **Dimension overlap.** Check the correlation table above before reading equal weights as balanced: any strongly correlated pair double-counts the same signal.
- **Accessibility is a proxy.** YOE and degree requirements are stated in a minority of postings (accuracy when stated ≈ 0.84 / 0.86); the dimension describes the jobs, not how hard the skill is to learn.
- **Breadth uses RCA > 1**, so a skill requested everywhere at similar rates (e.g. Communication) can have low breadth: breadth rewards being *over-represented* in many groups, not merely present.
- **Sample.** These tables come from a partial slice of the full run (the first 300k postings in URL order), not a random sample: the US is under-weighted and covers only job titles early in the alphabet. Use the full-run tables for decisions.

## References

- OECD & JRC (2008). *Handbook on Constructing Composite Indicators: Methodology and User Guide*. OECD Publishing, Paris.
- Saisana, M., Saltelli, A. & Tarantola, S. (2005). Uncertainty and sensitivity analysis techniques as tools for the quality assessment of composite indicators. *Journal of the Royal Statistical Society: Series A*, 168(2), 307–323.
- Diakoulaki, D., Mavrotas, G. & Papayannakis, L. (1995). Determining objective weights in multiple criteria problems: the CRITIC method. *Computers & Operations Research*, 22(7), 763–770.
- Alabdulkareem, A., Frank, M. R., Sun, L., AlShebli, B., Hidalgo, C. & Rahwan, I. (2018). Unpacking the polarization of workplace skills. *Science Advances*, 4(7), eaao6030.
- Dawson, N., Williams, M.-A. & Rizoiu, M.-A. (2021). Skill-driven recommendations for job transition pathways. *PLoS ONE*, 16(8), e0254722.
