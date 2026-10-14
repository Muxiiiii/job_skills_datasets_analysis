# Course priority: a composite ranking of skills for curriculum planning

Source: `outputs/full_v8 (1 file(s))` — 1,078,070 deduplicated postings, 280 specific skills with ≥ 100 postings. Generated 2026-10-14T10:44:49+00:00.

Reproduce with `python -m src.analysis.course_priority` (pilot) or `--preset full`. Tables are in `outputs/summary/full/course_priority/`.

## Method

**Unit and filters.** One posting per `dup_group_id`; generic and `(unspecified)` labels excluded; a skill needs ≥ 100 postings (same eligibility as the co-occurrence network in the curriculum analysis).

**Dimensions** (all oriented so that larger = higher priority):

| Dimension | Definition | Why it matters for a course |
|---|---|---|
| Demand | Share of deduplicated postings that mention the skill. | How many jobs the course serves. |
| Breadth | Number of the 12 occupation groups (`Other` excluded) where the skill's RCA > 1 with ≥ 20 postings in the group. | Transferability across fields. |
| Centrality | Weighted degree (sum of PMI edge weights) in the co-occurrence network: edge if lift > 1.5 and ≥ 30 co-occurring postings. PageRank is kept as an alternative (Spearman with weighted degree 0.97). | Skills that connect to many others anchor a bundle (Alabdulkareem et al. 2018). PMI is prevalence-adjusted, so very common skills score low here by construction (a skill in a share *s* of postings has lift ≤ 1/*s*); prevalence is carried by demand. |
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
| 3d | critic | 0.198 | 0.313 | 0.489 | – |
| 3d | entropy | 0.718 | 0.162 | 0.120 | – |
| 3d | equal | 0.333 | 0.333 | 0.333 | – |
| 4d | critic | 0.119 | 0.216 | 0.349 | 0.316 |
| 4d | entropy | 0.611 | 0.138 | 0.102 | 0.150 |
| 4d | equal | 0.250 | 0.250 | 0.250 | 0.250 |

Spearman correlation between the raw dimensions (high values mean two dimensions largely double-count):

| | demand | breadth | centrality | accessibility |
|---|---|---|---|---|
| demand | 1.00 | 0.32 | -0.26 | 0.29 |
| breadth | 0.32 | 1.00 | 0.13 | -0.07 |
| centrality | -0.26 | 0.13 | 1.00 | -0.68 |
| accessibility | 0.29 | -0.07 | -0.68 | 1.00 |

## Results (four dimensions)

| Equal-weight rank | Skill | Score | MC median rank | MC 5–95 % | P(top 10) | P(top 20) | Entropy rank | CRITIC rank |
|---|---|---|---|---|---|---|---|---|
| 1 | Communication | 0.513 | 16 | 1–261 | 0.47 | 0.54 | 1 | 127 |
| 2 | Teamwork | 0.511 | 8 | 2–250 | 0.52 | 0.58 | 2 | 95 |
| 3 | Written Communication | 0.508 | 9 | 1–100 | 0.54 | 0.66 | 9 | 5 |
| 4 | Problem Solving | 0.503 | 8 | 3–131 | 0.53 | 0.64 | 3 | 25 |
| 5 | Attention to Detail | 0.501 | 6 | 2–148 | 0.58 | 0.65 | 6 | 20 |
| 6 | Workplace / OSHA Safety | 0.491 | 13 | 4–124 | 0.47 | 0.64 | 5 | 16 |
| 7 | Mathematical Calculations | 0.490 | 14 | 2–61 | 0.37 | 0.64 | 24 | 1 |
| 8 | Microsoft Office | 0.472 | 13 | 6–104 | 0.44 | 0.59 | 7 | 21 |
| 9 | Power BI | 0.463 | 20 | 1–160 | 0.39 | 0.51 | 58 | 2 |
| 10 | Databases | 0.460 | 21 | 4–128 | 0.28 | 0.48 | 48 | 3 |
| 11 | Microsoft PowerPoint | 0.456 | 23 | 6–99 | 0.17 | 0.46 | 26 | 9 |
| 12 | Critical Thinking | 0.451 | 21 | 9–116 | 0.16 | 0.49 | 11 | 29 |
| 13 | Data Analysis | 0.450 | 22 | 10–118 | 0.07 | 0.44 | 16 | 11 |
| 14 | Data Visualization | 0.449 | 25 | 3–170 | 0.29 | 0.45 | 68 | 4 |
| 15 | Presentation Skills | 0.447 | 23 | 10–119 | 0.09 | 0.46 | 20 | 17 |
| 16 | Microsoft Excel | 0.442 | 27 | 12–89 | 0.01 | 0.29 | 13 | 24 |
| 17 | Customer Service | 0.437 | 32 | 3–212 | 0.33 | 0.41 | 4 | 71 |
| 18 | People Management | 0.436 | 27 | 10–139 | 0.06 | 0.39 | 10 | 38 |
| 19 | Time Management | 0.434 | 26 | 8–186 | 0.22 | 0.42 | 8 | 68 |
| 20 | Business Intelligence | 0.428 | 33 | 2–211 | 0.27 | 0.39 | 86 | 7 |
| 21 | Sustainability | 0.427 | 49 | 3–165 | 0.19 | 0.32 | 56 | 27 |
| 22 | SharePoint | 0.426 | 40 | 13–142 | 0.02 | 0.17 | 72 | 10 |
| 23 | Software Development | 0.425 | 37 | 13–145 | 0.01 | 0.28 | 36 | 12 |
| 24 | Automation | 0.424 | 45 | 4–196 | 0.28 | 0.36 | 65 | 8 |
| 25 | Microsoft Word | 0.424 | 40 | 12–113 | 0.02 | 0.24 | 33 | 32 |

**Stable top-10 skills** (P(top 10) ≥ 0.8 under random weights): none.

**Stable top-20 skills** (P(top 20) ≥ 0.8): none.

**Scaling sensitivity.** With percentile scaling instead of minmax, the equal-weight ranking has Kendall tau 0.678 with the one above and shares 3/10 of its top 10.

**Agreement between methods (4d):**

| Method A | Method B | Kendall tau | Top-10 overlap |
|---|---|---|---|
| equal | mc_median | 0.920 | 10/10 |
| equal | entropy | 0.718 | 7/10 |
| equal | critic | 0.806 | 4/10 |
| mc_median | entropy | 0.732 | 7/10 |
| mc_median | critic | 0.746 | 4/10 |
| entropy | critic | 0.558 | 1/10 |

**Agreement between methods (3d):**

| Method A | Method B | Kendall tau | Top-10 overlap |
|---|---|---|---|
| equal | mc_median | 0.966 | 8/10 |
| equal | entropy | 0.717 | 5/10 |
| equal | critic | 0.844 | 5/10 |
| mc_median | entropy | 0.736 | 6/10 |
| mc_median | critic | 0.831 | 3/10 |
| entropy | critic | 0.574 | 0/10 |

## Robustness: without accessibility (three dimensions)

Kendall tau between the 4d and 3d equal-weight rankings: 0.545; top-10 overlap 7/10.

| Equal-weight rank | Skill | Score | MC median rank | MC 5–95 % | P(top 10) | P(top 20) | Entropy rank | CRITIC rank |
|---|---|---|---|---|---|---|---|---|
| 1 | Teamwork | 0.548 | 6 | 1–255 | 0.54 | 0.59 | 2 | 94 |
| 2 | Written Communication | 0.546 | 8 | 1–95 | 0.60 | 0.70 | 9 | 14 |
| 3 | Communication | 0.542 | 12 | 1–267 | 0.49 | 0.55 | 1 | 108 |
| 4 | Problem Solving | 0.532 | 7 | 3–128 | 0.55 | 0.63 | 3 | 47 |
| 5 | Power BI | 0.527 | 7 | 1–55 | 0.55 | 0.72 | 43 | 1 |
| 6 | Attention to Detail | 0.526 | 5 | 2–142 | 0.59 | 0.65 | 4 | 45 |
| 7 | Business Intelligence | 0.525 | 9 | 2–58 | 0.53 | 0.69 | 45 | 2 |
| 8 | Data Visualization | 0.513 | 15 | 3–60 | 0.40 | 0.63 | 47 | 3 |
| 9 | Databases | 0.504 | 19 | 5–47 | 0.29 | 0.54 | 37 | 5 |
| 10 | Automation | 0.500 | 14 | 3–66 | 0.46 | 0.58 | 38 | 4 |
| 11 | Data Analysis | 0.495 | 18 | 10–48 | 0.09 | 0.60 | 15 | 13 |
| 12 | Project Management | 0.493 | 19 | 8–56 | 0.19 | 0.55 | 10 | 21 |
| 13 | Microsoft Office | 0.493 | 12 | 6–104 | 0.47 | 0.61 | 7 | 40 |
| 14 | Presentation Skills | 0.488 | 15 | 8–65 | 0.20 | 0.62 | 16 | 22 |
| 15 | Microsoft PowerPoint | 0.487 | 19 | 6–58 | 0.19 | 0.56 | 23 | 17 |

## By occupation group (four dimensions, equal weights)

Demand and centrality are recomputed inside each group (network over the group's postings, same thresholds; skills with ≥ 20 postings in the group); breadth and accessibility are the corpus-wide values.

| Occupation group | Postings | Top 8 (P(top 10) under random weights) |
|---|---|---|
| Creative Media | 15,408 | Workplace / OSHA Safety (0.91), Teamwork (0.60), Communication (0.53), Attention to Detail (0.71), Problem Solving (0.66), Microsoft Office (0.63), Time Management (0.47), People Management (0.32) |
| Education | 47,256 | Attention to Detail (0.87), Problem Solving (0.78), Teamwork (0.53), Communication (0.47), Microsoft Office (0.73), Workplace / OSHA Safety (0.52), Microsoft Excel (0.49), Written Communication (0.50) |
| Finance Accounting | 43,194 | Workplace / OSHA Safety (0.75), Attention to Detail (0.65), Communication (0.48), Teamwork (0.54), Written Communication (0.47), Problem Solving (0.53), Microsoft Office (0.41), Presentation Skills (0.37) |
| Healthcare Clinical | 122,328 | Teamwork (0.76), Communication (0.65), Problem Solving (0.88), Workplace / OSHA Safety (0.85), Attention to Detail (0.74), Written Communication (0.57), Microsoft Office (0.64), Customer Service (0.54) |
| Healthcare Nursing | 78,864 | Workplace / OSHA Safety (0.89), Problem Solving (0.82), Written Communication (0.61), Microsoft Office (0.56), Teamwork (0.52), Attention to Detail (0.40), Quality Improvement (0.41), Time Management (0.40) |
| Hospitality Food | 23,283 | Microsoft Office (0.59), Problem Solving (0.61), Sanitation (0.51), Customer Service (0.48), Workplace / OSHA Safety (0.53), Communication (0.47), Teamwork (0.50), People Management (0.43) |
| Legal Compliance | 11,071 | Problem Solving (0.94), Attention to Detail (0.87), Written Communication (0.72), Teamwork (0.63), Time Management (0.89), Microsoft Office (0.74), Presentation Skills (0.57), Microsoft Excel (0.51) |
| Management HR Admin | 187,232 | Communication (0.49), Teamwork (0.54), Workplace / OSHA Safety (0.54), Attention to Detail (0.55), Problem Solving (0.48), Mathematical Calculations (0.29), Written Communication (0.42), Critical Thinking (0.25) |
| Sales Customer | 98,257 | Communication (0.50), Teamwork (0.53), Workplace / OSHA Safety (0.53), Customer Service (0.46), Critical Thinking (0.57), Written Communication (0.49), Attention to Detail (0.56), Problem Solving (0.48) |
| Science Research | 13,654 | Teamwork (0.77), Workplace / OSHA Safety (0.77), Attention to Detail (0.70), Problem Solving (0.77), Communication (0.54), Written Communication (0.57), Data Analysis (0.50), Mathematical Calculations (0.47) |
| Skilled Trades Ops | 118,438 | Workplace / OSHA Safety (0.57), Communication (0.50), Teamwork (0.54), Problem Solving (0.56), Written Communication (0.51), Attention to Detail (0.58), Microsoft Office (0.53), Presentation Skills (0.41) |
| Tech Engineering | 74,999 | Workplace / OSHA Safety (0.80), Microsoft Office (0.78), Customer Service (0.54), Teamwork (0.52), Microsoft Excel (0.52), Attention to Detail (0.57), Time Management (0.42), People Management (0.28) |

## Limitations

- **No growth dimension.** The postings are a single snapshot (early 2024), so the ranking says nothing about rising or declining demand; a trend dimension needs a second period.
- **Extraction noise.** Skill precision ≈ 0.66, recall ≈ 0.58 on 50 unseen postings. Demand and co-occurrence inherit this error; small score differences are not meaningful, so read the rank intervals rather than the point ranks.
- **Choice of weight range.** The flat Dirichlet treats every weighting as equally plausible, including extreme ones (e.g. almost all weight on one dimension). Narrower priors (larger α) would give tighter intervals; the intervals here are therefore deliberately conservative. Entropy and CRITIC weights are properties of this data's spread, not statements about what matters for teaching.
- **Skewed demand.** A handful of skills appear in a large share of postings and most in under 3 %; min-max scaling compresses the long tail of demand, which is why entropy weighting puts most weight on demand. The scaling-sensitivity line above shows how much this matters.
- **Dimension overlap.** Check the correlation table above before reading equal weights as balanced: any strongly correlated pair double-counts the same signal.
- **Accessibility is a proxy.** YOE and degree requirements are stated in a minority of postings (accuracy when stated ≈ 0.84 / 0.86); the dimension describes the jobs, not how hard the skill is to learn.
- **Breadth uses RCA > 1**, so a skill requested everywhere at similar rates (e.g. Communication) can have low breadth: breadth rewards being *over-represented* in many groups, not merely present.
- **Sample.** Postings are those returned by LinkedIn searches in four English-speaking countries in early 2024; they are not a random sample of the labour market.

## References

- OECD & JRC (2008). *Handbook on Constructing Composite Indicators: Methodology and User Guide*. OECD Publishing, Paris.
- Saisana, M., Saltelli, A. & Tarantola, S. (2005). Uncertainty and sensitivity analysis techniques as tools for the quality assessment of composite indicators. *Journal of the Royal Statistical Society: Series A*, 168(2), 307–323.
- Diakoulaki, D., Mavrotas, G. & Papayannakis, L. (1995). Determining objective weights in multiple criteria problems: the CRITIC method. *Computers & Operations Research*, 22(7), 763–770.
- Alabdulkareem, A., Frank, M. R., Sun, L., AlShebli, B., Hidalgo, C. & Rahwan, I. (2018). Unpacking the polarization of workplace skills. *Science Advances*, 4(7), eaao6030.
- Dawson, N., Williams, M.-A. & Rizoiu, M.-A. (2021). Skill-driven recommendations for job transition pathways. *PLoS ONE*, 16(8), e0254722.
