# Curriculum insights: skill bundles and occupation-transition gaps

Source: `outputs/full_v8 (1 file(s))` — 1,078,070 deduplicated postings, 281 specific skills. Generated 2026-10-14T10:38:03+00:00.

Reproduce with `python -m src.analysis.curriculum` (add `--preset full` after the full run). Tables are in `outputs/summary/full/curriculum/`.

## Method

- **Unit and filters.** One posting per `dup_group_id`; generic and `(unspecified)` skill labels are excluded. Shares are shares of deduplicated postings (postings without any skill stay in the denominator).
- **RCA.** RCA(s, g) = share of postings in group g that mention s ÷ share of all postings that mention s. The table keeps RCA > 1 with at least 20 postings in the group.
- **Co-occurrence network.** Nodes: the top 300 skills by postings (each in ≥ 100 postings). Edge between two skills if lift > 1.5 and they co-occur in ≥ 30 postings; edge weight = PMI = log2(lift). Communities: Louvain (networkx, resolution 1.5, seed 42). A community is named after its three members with the highest within-community degree centrality.
- **Coverage.** Share of a group's postings that mention at least one skill of the community.
- **Stability.** Louvain re-run with seeds [0, 1, 2, 3, 4]; mean pairwise ARI and NMI between the partitions.
- **Occupation vectors.** Posting share of each skill with ≥ 50 postings overall (281 skills); the RCA-weighted variant multiplies each share by the skill's RCA in that group. Similarity is the cosine between two vectors.
- **Transition A→B.** Skills to add: share_B ≥ 3%, ranked by gap = share_B − share_A (top 15). Transferable skills: share ≥ 5% in both groups, ranked by the smaller share.
- The catch-all group `Other` is left out of group-level tables (its postings still count in overall shares).

## A. Skill bundles

The network has 280 skills and 11,145 edges (0 of the 280 candidate skills have no edge above the thresholds and are left out). Louvain finds **8 communities** (modularity 0.28).

**Stability across 5 seeds:** mean ARI 0.969 (min 0.942), mean NMI 0.961 (min 0.929); communities per seed: [8, 8, 8, 7, 7].

Sensitivity to the Louvain resolution (same graph, same seeds):

| Resolution | Communities per seed | Mean ARI | Mean NMI |
|---|---|---|---|
| 1 | [4, 4, 4, 4, 4] | 0.912 | 0.905 |
| 1.5 (used) | [8, 8, 8, 7, 7] | 0.969 | 0.961 |
| 2 | [13, 13, 12, 15, 12] | 0.821 | 0.828 |

| # | Community (top-3 central skills) | Skills | Postings covered | Strongest group (coverage) | Members (by centrality, first 10) |
|---|---|---|---|---|---|
| 1 | Diagnosis · Cultural Competence · Clinical Skills | 61 | 66.7% | Healthcare Nursing (94.7%) | Diagnosis, Cultural Competence, Clinical Skills, Stress Management, HIPAA, Quality Improvement, Assessment, Patient Education, Evidence-Based Practice, Care Planning … |
| 2 | Kubernetes · Docker · Jenkins | 51 | 19.0% | Tech Engineering (54.4%) | Kubernetes, Docker, Jenkins, Git, DevOps, Azure, Java, AWS, JavaScript, Cloud Computing … |
| 3 | Conflict Resolution · POS Systems · Cash Handling | 48 | 73.7% | Hospitality Food (93.3%) | Conflict Resolution, POS Systems, Cash Handling, Team Building, Performance Management, Payroll, People Management, Inventory Management, Coaching, Operations Management … |
| 4 | Electrical Systems · Inspection · Blueprints | 46 | 51.8% | Tech Engineering (79.8%) | Electrical Systems, Inspection, Blueprints, Commissioning, Repair, Welding, Reliability, Quality Control (Manufacturing), Workplace / OSHA Safety, Mechanical Engineering … |
| 5 | Accounting · Microsoft Excel · Microsoft PowerPoint | 33 | 49.3% | Finance Accounting (84.4%) | Accounting, Microsoft Excel, Microsoft PowerPoint, Accounts Payable, Financial Analysis, Forecasting, Microsoft Word, Microsoft Office, Variance Analysis, GAAP … |
| 6 | Initiative · Salesforce · Strategic Thinking | 29 | 40.8% | Legal Compliance (78.3%) | Initiative, Salesforce, Strategic Thinking, Presentation Skills, Social Media, Negotiation, Marketing, Creative Thinking, CRM, Microsoft Teams … |
| 7 | Data Visualization · Tableau · Data Science | 11 | 14.5% | Science Research (41.2%) | Data Visualization, Tableau, Data Science, Power BI, Statistics, Clinical Analysis, Data Analysis, Business Intelligence, Mathematical Calculations, R Programming … |
| 8 | Change Management | 1 | 1.7% | Creative Media (3.1%) | Change Management |

### Most distinctive skills per occupation group (top 8 by RCA)

| Occupation group | Skills (RCA) |
|---|---|
| Creative Media | Electrical Engineering (10.1), Content Marketing (8.2), Revit (8.0), Prototyping (7.8), MATLAB (7.3), AutoCAD (6.8), Commissioning (6.3), Architecture (5.1) |
| Education | Curriculum Development (8.6), Child Development (6.1), First Aid (3.1), Cultural Competence (2.7), Clinical Training (2.5), Public Relations (2.5), Psychology (2.4), Policy Development (2.3) |
| Finance Accounting | GAAP (18.4), Financial Statements (15.8), Accounts Payable (13.5), Variance Analysis (13.4), Accounts Receivable (11.9), Benefits Administration (10.9), Accounting (10.2), Financial Analysis (8.6) |
| Healthcare Clinical | Marriage and Family Therapy (8.0), Dental Hygiene (7.6), Radiology (5.5), Psychology (4.4), Social Work (3.7), Internal Medicine (3.6), Mental Health (3.4), Dentistry (3.3) |
| Healthcare Nursing | Care Planning (6.5), Nursing (6.4), Medication Administration (6.3), Wound Care (6.0), ACLS (5.5), Evidence-Based Practice (5.4), Infection Control (5.2), Critical Care (5.1) |
| Hospitality Food | Food Preparation (21.6), Food Service (16.6), Restaurant Management (14.0), Food Safety (11.6), Hospitality (8.4), POS Systems (6.0), Sanitation (5.8), Cost Control (4.4) |
| Legal Compliance | Litigation (54.3), Advocacy (9.7), Case Management (6.9), Real Estate Development (6.4), Negotiation (5.7), Writing (3.5), Filing (3.2), OneDrive (2.7) |
| Management HR Admin | Employee Relations (2.3), Performance Management (2.2), Content Marketing (2.1), Event Planning (2.0), Operations Management (2.0), Restaurant Management (1.9), People Management (1.9), SEO (1.8) |
| Sales Customer | Sales (7.3), Prospecting (6.6), CRM (5.1), SaaS (4.9), Cashiering (4.7), Salesforce (4.5), Loss Prevention (4.3), Retail / Store Operations (3.9) |
| Science Research | Clinical Analysis (38.0), Chemistry (24.4), R Programming (15.6), Instrumentation (10.0), Data Science (7.4), Statistics (4.9), Phlebotomy (4.9), Machine Learning (4.6) |
| Skilled Trades Ops | Carpentry (4.4), Welding (4.3), Equipment Operation (4.2), CMMS (4.1), Preventive Maintenance (4.0), Blueprints (4.0), Painting (3.8), Plumbing (3.7) |
| Tech Engineering | SolidWorks (9.6), Testing (9.3), Microservices (8.8), Docker (8.7), C# (8.6), Mechanical Engineering (8.1), Kubernetes (8.0), Git (7.8) |

## B. Occupation transitions

Cosine similarity between the 12 occupation groups (posting-share vectors):

| | Creative Media | Education | Finance Accounting | Healthcare Clinical | Healthcare Nursing | Hospitality Food | Legal Compliance | Management HR Admin | Sales Customer | Science Research | Skilled Trades Ops | Tech Engineering |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Creative Media | 1.00 | 0.84 | 0.71 | 0.57 | 0.39 | 0.65 | 0.63 | 0.87 | 0.79 | 0.80 | 0.87 | 0.96 |
| Education | 0.84 | 1.00 | 0.78 | 0.82 | 0.64 | 0.73 | 0.70 | 0.96 | 0.90 | 0.84 | 0.88 | 0.80 |
| Finance Accounting | 0.71 | 0.78 | 1.00 | 0.52 | 0.37 | 0.60 | 0.62 | 0.82 | 0.75 | 0.68 | 0.71 | 0.67 |
| Healthcare Clinical | 0.57 | 0.82 | 0.52 | 1.00 | 0.82 | 0.56 | 0.52 | 0.74 | 0.68 | 0.66 | 0.70 | 0.54 |
| Healthcare Nursing | 0.39 | 0.64 | 0.37 | 0.82 | 1.00 | 0.38 | 0.36 | 0.57 | 0.50 | 0.48 | 0.53 | 0.37 |
| Hospitality Food | 0.65 | 0.73 | 0.60 | 0.56 | 0.38 | 1.00 | 0.53 | 0.81 | 0.79 | 0.61 | 0.79 | 0.58 |
| Legal Compliance | 0.63 | 0.70 | 0.62 | 0.52 | 0.36 | 0.53 | 1.00 | 0.69 | 0.68 | 0.60 | 0.61 | 0.58 |
| Management HR Admin | 0.87 | 0.96 | 0.82 | 0.74 | 0.57 | 0.81 | 0.69 | 1.00 | 0.94 | 0.83 | 0.94 | 0.82 |
| Sales Customer | 0.79 | 0.90 | 0.75 | 0.68 | 0.50 | 0.79 | 0.68 | 0.94 | 1.00 | 0.73 | 0.86 | 0.72 |
| Science Research | 0.80 | 0.84 | 0.68 | 0.66 | 0.48 | 0.61 | 0.60 | 0.83 | 0.73 | 1.00 | 0.83 | 0.80 |
| Skilled Trades Ops | 0.87 | 0.88 | 0.71 | 0.70 | 0.53 | 0.79 | 0.61 | 0.94 | 0.86 | 0.83 | 1.00 | 0.84 |
| Tech Engineering | 0.96 | 0.80 | 0.67 | 0.54 | 0.37 | 0.58 | 0.58 | 0.82 | 0.72 | 0.80 | 0.84 | 1.00 |

**Posting-share vectors** — most similar: Creative Media ↔ Tech Engineering (0.96); Education ↔ Management HR Admin (0.96); Management HR Admin ↔ Sales Customer (0.94). Least similar: Healthcare Nursing ↔ Legal Compliance (0.36); Finance Accounting ↔ Healthcare Nursing (0.37); Healthcare Nursing ↔ Tech Engineering (0.37).

**Rca-weighted vectors** — most similar: Education ↔ Management HR Admin (0.78); Creative Media ↔ Tech Engineering (0.71); Management HR Admin ↔ Skilled Trades Ops (0.67). Least similar: Hospitality Food ↔ Legal Compliance (0.00); Healthcare Nursing ↔ Legal Compliance (0.00); Legal Compliance ↔ Science Research (0.00).

### Example: Creative Media → Tech Engineering

| Rank | Skill to add | Share in origin | Share in target | Gap |
|---|---|---|---|---|
| 1 | Mechanical Engineering | 4.2% | 11.9% | +7.7% |
| 2 | SQL | 4.0% | 10.3% | +6.3% |
| 3 | Computer Science | 6.3% | 12.5% | +6.3% |
| 4 | Python | 5.1% | 11.3% | +6.2% |
| 5 | Civil Engineering | 2.6% | 8.0% | +5.4% |
| 6 | Java | 3.1% | 8.1% | +5.0% |
| 7 | Testing | 1.2% | 6.0% | +4.8% |
| 8 | AWS | 3.2% | 8.0% | +4.7% |
| 9 | Software Development | 17.4% | 21.9% | +4.5% |
| 10 | Cybersecurity | 3.6% | 7.6% | +4.0% |
| 11 | JavaScript | 2.7% | 6.5% | +3.8% |
| 12 | Agile | 6.5% | 10.2% | +3.7% |
| 13 | Manufacturing | 14.7% | 18.5% | +3.7% |
| 14 | Git | 2.0% | 5.6% | +3.6% |
| 15 | Inspection | 2.3% | 5.5% | +3.2% |

Transferable: Communication (47% / 41%), Teamwork (42% / 39%), Project Management (32% / 28%), Problem Solving (26% / 26%), Workplace / OSHA Safety (20% / 21%), Production (22% / 18%), Software Development (17% / 22%), Attention to Detail (21% / 16%), Microsoft Office (17% / 16%), Architecture (15% / 16%), Manufacturing (15% / 18%), Electrical Systems (21% / 14%), Troubleshooting (13% / 15%), Written Communication (11% / 12%), Creativity (12% / 11%).

### Example: Tech Engineering → Creative Media

| Rank | Skill to add | Share in origin | Share in target | Gap |
|---|---|---|---|---|
| 1 | Electrical Systems | 13.9% | 21.1% | +7.1% |
| 2 | Marketing | 4.6% | 11.6% | +7.0% |
| 3 | Electrical Engineering | 10.2% | 17.0% | +6.8% |
| 4 | Time Management | 8.6% | 14.4% | +5.8% |
| 5 | Communication | 41.3% | 47.0% | +5.7% |
| 6 | Attention to Detail | 15.9% | 21.3% | +5.5% |
| 7 | Social Media | 0.6% | 5.8% | +5.2% |
| 8 | Project Management | 27.8% | 32.2% | +4.4% |
| 9 | Production | 17.5% | 21.7% | +4.1% |
| 10 | Budgeting | 5.5% | 9.2% | +3.7% |
| 11 | Customer Service | 7.6% | 11.2% | +3.6% |
| 12 | Scheduling | 6.3% | 9.7% | +3.3% |
| 13 | People Management | 5.9% | 8.9% | +3.0% |
| 14 | Teamwork | 38.7% | 41.7% | +3.0% |
| 15 | Content Marketing | 0.1% | 3.0% | +2.9% |

Transferable: Communication (41% / 47%), Teamwork (39% / 42%), Project Management (28% / 32%), Problem Solving (26% / 26%), Workplace / OSHA Safety (21% / 20%), Production (18% / 22%), Software Development (22% / 17%), Attention to Detail (16% / 21%), Microsoft Office (16% / 17%), Architecture (16% / 15%), Manufacturing (18% / 15%), Electrical Systems (14% / 21%), Troubleshooting (15% / 13%), Written Communication (12% / 11%), Creativity (11% / 12%).

### Finer view: top 50 search-position terms

Most similar pairs of position terms (posting-share vectors):

| Position A | Position B | Cosine |
|---|---|---|
| Anesthesiologist | Nurse Anesthetist | 0.99 |
| Christian Science Nurse | Nurse-Midwife | 0.99 |
| Nuclear Medicine Technologist | Radiologic Technologist | 0.98 |
| Christian Science Nurse | Nurse Practitioner | 0.98 |
| Christian Science Nurse | Nurse Office | 0.98 |
| Director Education | Director Educational Program | 0.98 |
| Nurse School | Nurse-Midwife | 0.98 |
| Nurse Practitioner | Nurse-Midwife | 0.97 |
| Christian Science Nurse | Nurse School | 0.97 |
| Nurse Anesthetist | Nurse-Midwife | 0.97 |

## Limitations

- **Skill extraction quality.** Precision ≈ 0.66, recall ≈ 0.58 on 50 unseen postings. Roughly one extracted skill in three is wrong, so rare co-occurrences and small gaps are noisy; read rankings and bundles, not individual percentages.
- **Sample.** Postings are those returned by LinkedIn searches in four English-speaking countries in early 2024; they are not a random sample of the labour market.
- **Narrow groups.** Some occupation groups are dominated by one or two search terms in this data, so their profile is the profile of those terms: Creative Media (Producer + Controls Designer = 58%); Legal Compliance (Lawyer + Insurance Attorney = 79%); Science Research (Biologist + Chemist = 64%).
- **Co-occurrence is not prerequisite structure.** Two skills in one community are requested together by employers; that says nothing about teaching order or dependency between them.
- **Shares, not importance.** A gap is a difference in how often postings mention a skill, not in the depth required. Occupation groups are broad and keyed on the LinkedIn search term, not the job content.
- **Thresholds matter.** The number of communities depends on the edge filters and the Louvain resolution; the stability figures above cover seed variation only.
