# Curriculum insights: skill bundles and occupation-transition gaps

Source: `outputs/full_v8/chunks (6 file(s))` — 259,589 deduplicated postings, 281 specific skills. Generated 2026-10-14T02:46:28+00:00.

Reproduce with `python -m src.analysis.curriculum` (add `--preset full` after the full run). Tables are in `outputs/summary/pilot/curriculum/`.

## Method

- **Unit and filters.** One posting per `dup_group_id`; generic and `(unspecified)` skill labels are excluded. Shares are shares of deduplicated postings (postings without any skill stay in the denominator).
- **RCA.** RCA(s, g) = share of postings in group g that mention s ÷ share of all postings that mention s. The table keeps RCA > 1 with at least 20 postings in the group.
- **Co-occurrence network.** Nodes: the top 300 skills by postings (each in ≥ 100 postings). Edge between two skills if lift > 1.5 and they co-occur in ≥ 30 postings; edge weight = PMI = log2(lift). Communities: Louvain (networkx, resolution 1.5, seed 42). A community is named after its three members with the highest within-community degree centrality.
- **Coverage.** Share of a group's postings that mention at least one skill of the community.
- **Stability.** Louvain re-run with seeds [0, 1, 2, 3, 4]; mean pairwise ARI and NMI between the partitions.
- **Occupation vectors.** Posting share of each skill with ≥ 50 postings overall (280 skills); the RCA-weighted variant multiplies each share by the skill's RCA in that group. Similarity is the cosine between two vectors.
- **Transition A→B.** Skills to add: share_B ≥ 3%, ranked by gap = share_B − share_A (top 15). Transferable skills: share ≥ 5% in both groups, ranked by the smaller share.
- The catch-all group `Other` is left out of group-level tables (its postings still count in overall shares).

## A. Skill bundles

The network has 278 skills and 8,922 edges (0 of the 278 candidate skills have no edge above the thresholds and are left out). Louvain finds **7 communities** (modularity 0.33).

**Stability across 5 seeds:** mean ARI 0.980 (min 0.965), mean NMI 0.975 (min 0.957); communities per seed: [8, 7, 8, 7, 7].

Sensitivity to the Louvain resolution (same graph, same seeds):

| Resolution | Communities per seed | Mean ARI | Mean NMI |
|---|---|---|---|
| 1 | [4, 4, 4, 5, 5] | 0.838 | 0.902 |
| 1.5 (used) | [8, 7, 8, 7, 7] | 0.980 | 0.975 |
| 2 | [11, 11, 12, 11, 12] | 0.837 | 0.853 |

| # | Community (top-3 central skills) | Skills | Postings covered | Strongest group (coverage) | Members (by centrality, first 10) |
|---|---|---|---|---|---|
| 1 | Electrical Systems · Reliability · Inspection | 59 | 59.0% | Creative Media (83.8%) | Electrical Systems, Reliability, Inspection, Mechanical Engineering, Commissioning, Quality Assurance, Technical Support, Workplace / OSHA Safety, Electrical Engineering, Manufacturing … |
| 2 | Diagnosis · Clinical Skills · Assessment | 54 | 42.5% | Healthcare Nursing (95.0%) | Diagnosis, Clinical Skills, Assessment, Physical Therapy, Patient Care, Nursing, Quality Improvement, Counseling, Mental Health, CPR … |
| 3 | Computer Science · Software Development · SQL | 51 | 18.9% | Tech Engineering (44.1%) | Computer Science, Software Development, SQL, Architecture, DevOps, Git, Java, AWS, Cloud Computing, Python … |
| 4 | Conflict Resolution · Cash Handling · Retail / Store Operations | 46 | 72.7% | Hospitality Food (90.4%) | Conflict Resolution, Cash Handling, Retail / Store Operations, Scheduling, People Management, Inventory Management, Merchandising, Staffing, Retail Operations, Performance Management … |
| 5 | Microsoft Excel · Microsoft PowerPoint · Attention to Detail | 36 | 56.1% | Finance Accounting (88.0%) | Microsoft Excel, Microsoft PowerPoint, Attention to Detail, Written Communication, Microsoft Outlook, Microsoft Word, Accounting, SAP, Microsoft Office, Critical Thinking … |
| 6 | Strategic Thinking · Initiative · Social Media | 30 | 62.9% | Sales Customer (83.7%) | Strategic Thinking, Initiative, Social Media, Marketing, Presentation Skills, Prospecting, CRM, Creative Thinking, Sales, Negotiation … |
| 7 | Mathematical Calculations · Statistics | 2 | 3.2% | Science Research (10.1%) | Mathematical Calculations, Statistics |

### Most distinctive skills per occupation group (top 8 by RCA)

| Occupation group | Skills (RCA) |
|---|---|
| Creative Media | Electrical Engineering (9.0), Prototyping (9.0), MATLAB (8.1), Content Marketing (6.9), Revit (6.8), AutoCAD (6.3), Instrumentation (5.6), Commissioning (5.4) |
| Education | Curriculum Development (8.0), Child Development (4.3), Cultural Competence (3.9), Clinical Training (3.7), Psychology (2.8), First Aid (2.5), Statistics (2.4), Artificial Intelligence (2.3) |
| Finance Accounting | GAAP (12.1), Financial Statements (11.1), Accounts Payable (9.5), Variance Analysis (9.3), Accounts Receivable (9.0), Accounting (8.2), Auditing (7.1), Financial Analysis (7.0) |
| Healthcare Clinical | Dental Hygiene (10.4), Marriage and Family Therapy (7.1), Radiology (6.7), Surgery (6.5), Dentistry (6.3), Psychology (5.9), Internal Medicine (5.4), Social Work (4.9) |
| Healthcare Nursing | Medication Administration (13.7), Vital Signs (12.8), Nursing (11.9), Wound Care (11.8), Infection Control (11.2), Phlebotomy (11.0), Care Planning (10.9), Clinical Quality (9.5) |
| Hospitality Food | Food Preparation (19.3), Food Service (11.3), Food Safety (10.2), Restaurant Management (9.5), Hospitality (6.8), Sanitation (5.6), Stocking (4.4), POS Systems (3.9) |
| Legal Compliance | Litigation (40.2), Advocacy (11.0), Case Management (10.5), Real Estate Development (5.5), Negotiation (4.1), Writing (2.7), Insurance (2.6), Business / Org Development (2.1) |
| Management HR Admin | Employee Relations (2.4), Loss Prevention (2.2), Restaurant Management (2.1), Performance Management (2.0), SEO (1.9), Cash Handling (1.9), Operations Management (1.9), Content Marketing (1.9) |
| Sales Customer | Sales (6.9), Prospecting (6.3), SaaS (5.8), Salesforce (5.2), CRM (4.8), Cashiering (4.2), Insurance (3.3), Negotiation (2.9) |
| Science Research | Clinical Analysis (52.0), Chemistry (29.3), Instrumentation (9.8), Data Science (6.9), MATLAB (5.8), Machine Learning (5.7), Product Development (5.0), Statistics (4.7) |
| Skilled Trades Ops | Equipment Operation (4.9), CMMS (4.5), Preventive Maintenance (4.2), Welding (4.0), Painting (4.0), Blueprints (3.9), Carpentry (3.9), Inspection (3.6) |
| Tech Engineering | Testing (9.2), Microservices (8.6), SolidWorks (8.3), Docker (8.0), C# (7.9), Kubernetes (7.4), Version Control (7.4), Revit (7.4) |

## B. Occupation transitions

Cosine similarity between the 12 occupation groups (posting-share vectors):

| | Creative Media | Education | Finance Accounting | Healthcare Clinical | Healthcare Nursing | Hospitality Food | Legal Compliance | Management HR Admin | Sales Customer | Science Research | Skilled Trades Ops | Tech Engineering |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Creative Media | 1.00 | 0.86 | 0.67 | 0.65 | 0.45 | 0.70 | 0.64 | 0.88 | 0.78 | 0.84 | 0.90 | 0.97 |
| Education | 0.86 | 1.00 | 0.74 | 0.86 | 0.64 | 0.78 | 0.73 | 0.94 | 0.87 | 0.87 | 0.88 | 0.84 |
| Finance Accounting | 0.67 | 0.74 | 1.00 | 0.55 | 0.39 | 0.62 | 0.60 | 0.80 | 0.71 | 0.67 | 0.70 | 0.65 |
| Healthcare Clinical | 0.65 | 0.86 | 0.55 | 1.00 | 0.81 | 0.65 | 0.60 | 0.76 | 0.69 | 0.71 | 0.72 | 0.65 |
| Healthcare Nursing | 0.45 | 0.64 | 0.39 | 0.81 | 1.00 | 0.44 | 0.42 | 0.55 | 0.49 | 0.51 | 0.52 | 0.45 |
| Hospitality Food | 0.70 | 0.78 | 0.62 | 0.65 | 0.44 | 1.00 | 0.58 | 0.87 | 0.78 | 0.67 | 0.85 | 0.66 |
| Legal Compliance | 0.64 | 0.73 | 0.60 | 0.60 | 0.42 | 0.58 | 1.00 | 0.71 | 0.71 | 0.64 | 0.65 | 0.62 |
| Management HR Admin | 0.88 | 0.94 | 0.80 | 0.76 | 0.55 | 0.87 | 0.71 | 1.00 | 0.91 | 0.83 | 0.95 | 0.84 |
| Sales Customer | 0.78 | 0.87 | 0.71 | 0.69 | 0.49 | 0.78 | 0.71 | 0.91 | 1.00 | 0.75 | 0.84 | 0.75 |
| Science Research | 0.84 | 0.87 | 0.67 | 0.71 | 0.51 | 0.67 | 0.64 | 0.83 | 0.75 | 1.00 | 0.83 | 0.84 |
| Skilled Trades Ops | 0.90 | 0.88 | 0.70 | 0.72 | 0.52 | 0.85 | 0.65 | 0.95 | 0.84 | 0.83 | 1.00 | 0.87 |
| Tech Engineering | 0.97 | 0.84 | 0.65 | 0.65 | 0.45 | 0.66 | 0.62 | 0.84 | 0.75 | 0.84 | 0.87 | 1.00 |

**Posting-share vectors** — most similar: Creative Media ↔ Tech Engineering (0.97); Management HR Admin ↔ Skilled Trades Ops (0.95); Education ↔ Management HR Admin (0.94). Least similar: Finance Accounting ↔ Healthcare Nursing (0.39); Healthcare Nursing ↔ Legal Compliance (0.42); Healthcare Nursing ↔ Hospitality Food (0.44).

**Rca-weighted vectors** — most similar: Creative Media ↔ Tech Engineering (0.73); Management HR Admin ↔ Skilled Trades Ops (0.70); Education ↔ Management HR Admin (0.68). Least similar: Legal Compliance ↔ Science Research (0.00); Healthcare Nursing ↔ Legal Compliance (0.00); Hospitality Food ↔ Legal Compliance (0.00).

### Example: Creative Media → Tech Engineering

| Rank | Skill to add | Share in origin | Share in target | Gap |
|---|---|---|---|---|
| 1 | Mechanical Engineering | 3.5% | 9.6% | +6.1% |
| 2 | Civil Engineering | 2.9% | 8.0% | +5.0% |
| 3 | SQL | 2.9% | 7.7% | +4.8% |
| 4 | Python | 3.8% | 8.2% | +4.4% |
| 5 | Computer Science | 3.6% | 8.0% | +4.3% |
| 6 | AWS | 2.2% | 6.2% | +4.0% |
| 7 | Testing | 0.6% | 4.5% | +4.0% |
| 8 | Software Development | 13.3% | 17.0% | +3.7% |
| 9 | Java | 2.2% | 5.7% | +3.6% |
| 10 | JavaScript | 2.1% | 5.4% | +3.3% |
| 11 | Git | 1.5% | 4.7% | +3.3% |
| 12 | Agile | 6.2% | 9.2% | +3.0% |
| 13 | Cybersecurity | 2.8% | 5.3% | +2.5% |
| 14 | DevOps | 2.1% | 4.5% | +2.4% |
| 15 | Azure | 1.3% | 3.7% | +2.3% |

Transferable: Communication (47% / 42%), Teamwork (41% / 38%), Project Management (33% / 27%), Problem Solving (25% / 24%), Workplace / OSHA Safety (22% / 20%), Production (21% / 15%), Architecture (14% / 15%), Attention to Detail (20% / 14%), Software Development (13% / 17%), Electrical Systems (19% / 13%), Microsoft Office (14% / 13%), Creativity (13% / 12%), Manufacturing (12% / 14%), Interpersonal Skills (13% / 11%), Driving (10% / 10%).

### Example: Tech Engineering → Creative Media

| Rank | Skill to add | Share in origin | Share in target | Gap |
|---|---|---|---|---|
| 1 | Marketing | 4.0% | 11.0% | +7.1% |
| 2 | Electrical Systems | 12.7% | 19.2% | +6.5% |
| 3 | Electrical Engineering | 7.4% | 13.8% | +6.5% |
| 4 | Project Management | 27.4% | 33.3% | +5.8% |
| 5 | Attention to Detail | 13.9% | 19.5% | +5.6% |
| 6 | Production | 15.4% | 21.0% | +5.5% |
| 7 | Time Management | 9.1% | 14.5% | +5.4% |
| 8 | Social Media | 0.8% | 5.9% | +5.1% |
| 9 | Communication | 42.1% | 46.6% | +4.4% |
| 10 | People Management | 6.1% | 10.0% | +3.9% |
| 11 | Scheduling | 4.1% | 7.8% | +3.8% |
| 12 | Budgeting | 5.4% | 9.0% | +3.6% |
| 13 | Content Marketing | 0.2% | 3.6% | +3.4% |
| 14 | Teamwork | 38.4% | 41.3% | +3.0% |
| 15 | Merchandising | 0.8% | 3.1% | +2.3% |

Transferable: Communication (42% / 47%), Teamwork (38% / 41%), Project Management (27% / 33%), Problem Solving (24% / 25%), Workplace / OSHA Safety (20% / 22%), Production (15% / 21%), Architecture (15% / 14%), Attention to Detail (14% / 20%), Software Development (17% / 13%), Electrical Systems (13% / 19%), Microsoft Office (13% / 14%), Creativity (12% / 13%), Manufacturing (14% / 12%), Interpersonal Skills (11% / 13%), Driving (10% / 10%).

### Finer view: top 50 search-position terms

Most similar pairs of position terms (posting-share vectors):

| Position A | Position B | Cosine |
|---|---|---|
| Abstractor | Administrative Clerk | 0.99 |
| Christian Science Nurse | Nurse Practitioner | 0.99 |
| Director Stage | Manager Display | 0.98 |
| Accountant | Controller | 0.97 |
| Change Person | Model | 0.97 |
| Change Person | Consultant Education | 0.97 |
| Extra | Guide | 0.97 |
| Guide | Principal | 0.97 |
| Driver | Driver Supervisor | 0.97 |
| Manager Benefits | Manager Employment | 0.97 |

## Limitations

- **Skill extraction quality.** Precision ≈ 0.66, recall ≈ 0.58 on 50 unseen postings. Roughly one extracted skill in three is wrong, so rare co-occurrences and small gaps are noisy; read rankings and bundles, not individual percentages.
- **Sample.** These tables come from a partial slice of the full run (the first postings in URL order), not a random sample: the US is under-weighted and covers only job titles early in the alphabet. Treat every figure as provisional until the full run is in.
- **Narrow groups.** Some occupation groups are dominated by one or two search terms in this data, so their profile is the profile of those terms: Creative Media (Producer + Controls Designer = 55%); Hospitality Food (Chef + Bakery Supervisor = 57%); Legal Compliance (Lawyer + Insurance Attorney = 84%); Science Research (Biologist + Chemist = 62%).
- **Co-occurrence is not prerequisite structure.** Two skills in one community are requested together by employers; that says nothing about teaching order or dependency between them.
- **Shares, not importance.** A gap is a difference in how often postings mention a skill, not in the depth required. Occupation groups are broad and keyed on the LinkedIn search term, not the job content.
- **Thresholds matter.** The number of communities depends on the edge filters and the Louvain resolution; the stability figures above cover seed variation only.
