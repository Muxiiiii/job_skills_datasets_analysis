# Models report — skill profiles and occupation-group prediction

Input: 213,856 deduplicated postings with ≥3 specific skills × 280 skills
(skills appearing in ≥50 postings; generic / unspecified labels excluded). Source: `outputs/full_v8/chunks (6 file(s))`.

> Skill extraction precision≈0.66 / recall≈0.58 on 50 unseen postings (two-source high-confidence subset: precision≈0.93). Use for rankings and group comparisons, not as per-posting skill lists.
> Extraction noise (precision≈0.66) blurs both the clusters and the classifier; treat results as descriptive.

## (a) Skill profiles: TF-IDF → NMF / KMeans

Binary posting × skill matrix, TF-IDF weighted (IDF down-weights ubiquitous skills such as Communication).
k was searched over [6, 8, 10, 12, 14, 16]: NMF by mean UMass topic coherence of each topic's top-10 skills (higher is better),
KMeans by cosine silhouette on a 10,000-posting sample.

| k | nmf_umass_coherence | nmf_topic_diversity | nmf_recon_err | kmeans_silhouette_cosine | kmeans_inertia |
|---|---|---|---|---|---|
| 6 | -1.923 | 0.917 | 423.555 | 0.043 | 186725.375 |
| 8 | -1.976 | 0.887 | 417.806 | 0.046 | 184570.906 |
| 10 | -2.029 | 0.790 | 412.388 | 0.055 | 180944.812 |
| 12 | -2.141 | 0.742 | 406.883 | 0.059 | 179630.406 |
| 14 | -2.254 | 0.707 | 401.669 | 0.053 | 178087.266 |
| 16 | -2.344 | 0.688 | 397.225 | 0.063 | 175522.375 |

Selected: **NMF k=6** (best coherence), **KMeans k=16** (best silhouette).
**Note:** the selected k for NMF and KMeans sits on the edge of the search grid, i.e. the criterion is monotone over this range rather than peaking (coherence favours fewer topics, silhouette more clusters; a wider 4–24 grid on the pilot showed the same trend). The data do not single out a k; treat these as convenient resolutions, not as the 'true' number of skill profiles.
Silhouette values are low in absolute terms, which is expected for sparse, overlapping skill sets: postings do not
form well-separated clusters, so the profiles are best read as soft themes.

### NMF topics (k=6) — top 15 skills each

Size = postings whose largest topic weight is this topic.

- **topic 3** — 52,911 postings (24.7%); mostly Tech Engineering 21%, Management HR Admin 21%, Other 20%
  - Workplace / OSHA Safety, Project Management, Production, Manufacturing, Quality Assurance, Process Improvement, Electrical Systems, Repair, Risk Management, Driving, Creativity, Supply Chain, Inspection, Troubleshooting, People Management
- **topic 2** — 39,704 postings (18.6%); mostly Management HR Admin 32%, Other 23%, Sales Customer 14%
  - Customer Service, People Management, Inventory Management, Merchandising, Sanitation, Communication, Coaching, Retail Operations, Driving, Scheduling, Computer Proficiency, Retail / Store Operations, Food Preparation, Customer Focus, Adaptability
- **topic 1** — 35,269 postings (16.5%); mostly Healthcare Nursing 25%, Healthcare Clinical 25%, Other 17%
  - Nursing, Patient Care, Assessment, Diagnosis, Mental Health, Professional Development, Clinical Skills, Teamwork, Physical Therapy, Care Planning, Quality Improvement, CPR, Communication, BLS, Surgery
- **topic 5** — 29,334 postings (13.7%); mostly Finance Accounting 33%, Management HR Admin 24%, Other 21%
  - Microsoft Excel, Accounting, Microsoft Office, Microsoft Word, Microsoft Outlook, Microsoft PowerPoint, Written Communication, Budgeting, Auditing, Financial Statements, Financial Analysis, Attention to Detail, Accounts Payable, Billing, Computer Proficiency
- **topic 0** — 29,118 postings (13.6%); mostly Other 26%, Management HR Admin 22%, Skilled Trades Ops 9%
  - Problem Solving, Teamwork, Time Management, Attention to Detail, Communication, Interpersonal Skills, Critical Thinking, Initiative, Decision Making, Adaptability, Multitasking, Microsoft Office, Data Analysis, Conflict Resolution, Creativity
- **topic 4** — 27,520 postings (12.9%); mostly Sales Customer 42%, Management HR Admin 19%, Other 19%
  - Sales, Marketing, Negotiation, CRM, Presentation Skills, Prospecting, Interpersonal Skills, Business / Org Development, Driving, Networking, Social Media, Salesforce, Communication, Microsoft Office, Data Analysis

### KMeans clusters (k=16) — top 15 skills by centroid weight

- **cluster 10** — 35,168 postings (16.4%); mostly Other 26%, Management HR Admin 24%, Education 9%
  - Communication, Teamwork, Interpersonal Skills, Problem Solving, Project Management, Attention to Detail, Workplace / OSHA Safety, Critical Thinking, Assessment, Microsoft Office, Time Management, Data Analysis, Risk Management, Negotiation, Writing
- **cluster 14** — 20,305 postings (9.5%); mostly Management HR Admin 33%, Other 23%, Sales Customer 16%
  - Customer Service, Communication, Problem Solving, Teamwork, Merchandising, Time Management, Attention to Detail, People Management, Inventory Management, Retail Operations, Retail / Store Operations, Microsoft Office, Coaching, Workplace / OSHA Safety, Scheduling
- **cluster 7** — 17,392 postings (8.1%); mostly Healthcare Nursing 41%, Healthcare Clinical 21%, Other 14%
  - Nursing, Patient Care, Teamwork, Diagnosis, Assessment, Communication, Clinical Skills, BLS, Care Planning, Surgery, Quality Improvement, CPR, Medication Administration, Physical Therapy, Internal Medicine
- **cluster 6** — 14,771 postings (6.9%); mostly Finance Accounting 61%, Management HR Admin 19%, Other 13%
  - Accounting, Financial Statements, Auditing, Attention to Detail, Microsoft Excel, Financial Analysis, Budgeting, Accounts Payable, Communication, GAAP, Microsoft Office, Forecasting, Problem Solving, Critical Thinking, Teamwork
- **cluster 5** — 14,086 postings (6.6%); mostly Management HR Admin 30%, Other 26%, Sales Customer 12%
  - Microsoft Excel, Microsoft Word, Microsoft PowerPoint, Microsoft Outlook, Microsoft Office, Attention to Detail, Communication, Teamwork, Time Management, Customer Service, Problem Solving, Written Communication, Interpersonal Skills, Computer Proficiency, Initiative
- **cluster 3** — 13,731 postings (6.4%); mostly Skilled Trades Ops 26%, Management HR Admin 25%, Other 18%
  - Production, Manufacturing, Quality Assurance, Workplace / OSHA Safety, Process Improvement, Communication, Teamwork, Problem Solving, Project Management, Attention to Detail, Quality Control (Manufacturing), Supply Chain, People Management, Inspection, Lean / Six Sigma
- **cluster 9** — 12,272 postings (5.7%); mostly Tech Engineering 36%, Skilled Trades Ops 19%, Management HR Admin 16%
  - Electrical Systems, Project Management, AutoCAD, Electrical Engineering, Civil Engineering, Workplace / OSHA Safety, Mechanical Engineering, Communication, Teamwork, Architecture, Revit, Troubleshooting, Creativity, Commissioning, Construction Management
- **cluster 11** — 12,153 postings (5.7%); mostly Sales Customer 72%, Other 13%, Management HR Admin 9%
  - Sales, CRM, Prospecting, Negotiation, Communication, Customer Service, Marketing, Business / Org Development, Presentation Skills, Interpersonal Skills, Teamwork, Driving, Microsoft Office, Problem Solving, Time Management
- **cluster 15** — 11,770 postings (5.5%); mostly Tech Engineering 37%, Other 25%, Management HR Admin 12%
  - Software Development, Python, SQL, Computer Science, Agile, Architecture, AWS, Java, Teamwork, Communication, Cybersecurity, JavaScript, Automation, DevOps, Problem Solving
- **cluster 13** — 11,062 postings (5.2%); mostly Other 23%, Management HR Admin 20%, Healthcare Clinical 14%
  - Professional Development, Coaching, Teamwork, Communication, Assessment, Workplace / OSHA Safety, People Management, Interpersonal Skills, Problem Solving, Creativity, Staff Development, Social Work, Project Management, Adaptability, Driving
- **cluster 8** — 9,990 postings (4.7%); mostly Management HR Admin 31%, Other 21%, Hospitality Food 21%
  - Sanitation, Food Preparation, Customer Service, Workplace / OSHA Safety, Communication, Teamwork, Inventory Management, People Management, Attention to Detail, Problem Solving, Food Service, Scheduling, Time Management, Food Safety, Driving
- **cluster 2** — 9,226 postings (4.3%); mostly Other 31%, Management HR Admin 21%, Sales Customer 12%
  - Adaptability, Driving, Communication, Computer Proficiency, Customer Service, Teamwork, Workplace / OSHA Safety, Attention to Detail, Problem Solving, Time Management, Interpersonal Skills, People Management, Microsoft Office, Initiative, Coaching
- **cluster 1** — 8,902 postings (4.2%); mostly Management HR Admin 34%, Other 24%, Sales Customer 17%
  - Marketing, Social Media, Communication, Teamwork, Project Management, Content Marketing, Attention to Detail, Interpersonal Skills, Data Analysis, Presentation Skills, Microsoft Office, Time Management, Customer Service, Problem Solving, SEO
- **cluster 12** — 8,290 postings (3.9%); mostly Skilled Trades Ops 39%, Management HR Admin 18%, Other 18%
  - Repair, Workplace / OSHA Safety, Electrical Systems, Driving, Customer Service, Troubleshooting, Communication, Teamwork, Inspection, Problem Solving, Attention to Detail, Preventive Maintenance, Project Management, Production, Customer Focus
- **cluster 0** — 7,932 postings (3.7%); mostly Healthcare Clinical 31%, Management HR Admin 15%, Healthcare Nursing 15%
  - Mental Health, Diagnosis, Assessment, Nursing, Psychology, Teamwork, Counseling, Communication, Professional Development, Social Work, Physical Therapy, People Management, Care Planning, Workplace / OSHA Safety, Case Management
- **cluster 4** — 6,806 postings (3.2%); mostly Management HR Admin 27%, Other 22%, Sales Customer 18%
  - Customer Focus, Business / Org Development, Customer Service, Communication, Teamwork, Interpersonal Skills, Problem Solving, Marketing, People Management, Driving, Time Management, Attention to Detail, Project Management, Microsoft Office, Coaching

## (b) Predicting occupation group from the skill set

Multinomial logistic regression (TF-IDF features, `class_weight="balanced"`, C=1.0) on 12 groups
(excluding the catch-all `Other`), stratified 135,585 train / 33,897 test.
The label `position_group` comes from LinkedIn's `search_position`, not from the description, so the target is
independent of the extracted skills.

| metric | logistic regression | majority-class baseline |
|---|---|---|
| accuracy | **0.443** | 0.275 |
| macro-F1 | **0.435** | 0.036 |
| weighted-F1 | 0.435 | — |

### Per-class test performance

| position_group | precision | recall | f1 | support |
|---|---|---|---|---|
| Healthcare_Nursing | 0.622 | 0.872 | 0.726 | 1870 |
| Finance_Accounting | 0.625 | 0.738 | 0.677 | 2934 |
| Sales_Customer | 0.650 | 0.496 | 0.563 | 4973 |
| Healthcare_Clinical | 0.511 | 0.601 | 0.552 | 2463 |
| Tech_Engineering | 0.512 | 0.505 | 0.509 | 3338 |
| Skilled_Trades_Ops | 0.463 | 0.396 | 0.427 | 4325 |
| Legal_Compliance | 0.269 | 0.859 | 0.410 | 490 |
| Hospitality_Food | 0.225 | 0.723 | 0.343 | 958 |
| Education | 0.255 | 0.343 | 0.292 | 2064 |
| Science_Research | 0.173 | 0.656 | 0.274 | 407 |
| Management_HR_Admin | 0.576 | 0.157 | 0.247 | 9331 |
| Creative_Media | 0.129 | 0.458 | 0.202 | 744 |

### 10 most important skills per group (largest positive coefficients)

- **Management HR Admin**: Employee Relations, Sales, SEO, Administrative Support, Restaurant Management, Accounting, Filing, Food Preparation, People Management, Social Work
- **Sales Customer**: Sales, Cashiering, Customer Service, Prospecting, SaaS, CRM, Insurance, Evidence-Based Practice, Salesforce, Retail / Store Operations
- **Skilled Trades Ops**: Civil Engineering, Electrical Systems, Repair, Testing, Forklift Operation, Equipment Operation, Inspection, Production, Preventive Maintenance, Blueprints
- **Tech Engineering**: Testing, Architecture, Mechanical Engineering, Civil Engineering, Revit, AutoCAD, SolidWorks, JavaScript, Project Management, Electrical Systems
- **Finance Accounting**: Accounting, Financial Statements, GAAP, Auditing, Accounts Payable, Microsoft Excel, Benefits Administration, Employee Relations, Forklift Operation, Payroll
- **Healthcare Clinical**: Surgery, Social Work, Patient Care, Psychology, Radiology, Clinical Skills, Dentistry, Diagnosis, Critical Care, Internal Medicine
- **Education**: Curriculum Development, Clinical Training, First Aid, Psychology, Assessment, Clinical Skills, Technical / Product Training, Physical Security, Mathematical Calculations, Social Work
- **Healthcare Nursing**: Nursing, Patient Care, Medication Administration, Clinical Skills, Care Planning, Surgery, Infection Control, Clinical Quality, Vital Signs, Phlebotomy
- **Hospitality Food**: Food Preparation, Restaurant Management, Food Safety, Customer Service, Hospitality, Sanitation, Merchandising, Food Service, Inventory Management, Production
- **Creative Media**: Architecture, Prototyping, Electrical Engineering, AutoCAD, Content Marketing, Electrical Systems, Project Management, Production, Merchandising, MATLAB
- **Legal Compliance**: Litigation, Case Management, Negotiation, Advocacy, Real Estate Development, Filing, Computer Science, Business / Org Development, Attention to Detail, Procurement
- **Science Research**: Clinical Analysis, Chemistry, Data Analysis, Troubleshooting, Instrumentation, Python, Machine Learning, Oncology, Quality Assurance, Product Development

### Most frequent confusions (true → predicted, test set)

| true | predicted | n |
|---|---|---|
| Management_HR_Admin | Hospitality_Food | 1272 |
| Management_HR_Admin | Skilled_Trades_Ops | 992 |
| Management_HR_Admin | Education | 961 |
| Management_HR_Admin | Finance_Accounting | 878 |
| Management_HR_Admin | Creative_Media | 806 |
| Management_HR_Admin | Sales_Customer | 743 |
| Tech_Engineering | Creative_Media | 689 |
| Management_HR_Admin | Tech_Engineering | 664 |

## Caveats

- The pilot slice is not a random sample of the corpus (URL-ordered: AU/CA/UK complete, US only early-alphabet titles); re-run with `--preset full`.
- `position_group` is a coarse mapping of 1,993 search positions; `Management_HR_Admin` in particular is heterogeneous, which caps accuracy.
- Coefficients show association with a group relative to the others, not importance of the skill in absolute demand.
