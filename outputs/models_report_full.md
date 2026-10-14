# Models report — skill profiles and occupation-group prediction

Input: 300,000 deduplicated postings with ≥3 specific skills × 281 skills
(skills appearing in ≥50 postings; generic / unspecified labels excluded). Source: `outputs/full_v8 (1 file(s))`.
Random sample of 300,000 of 886,966 eligible postings (seed 42, `--max-jobs`).

> Skill extraction precision≈0.66 / recall≈0.58 on 50 unseen postings (two-source high-confidence subset: precision≈0.93). Use for rankings and group comparisons, not as per-posting skill lists.
> Extraction noise (precision≈0.66) blurs both the clusters and the classifier; treat results as descriptive.

## (a) Skill profiles: TF-IDF → NMF / KMeans

Binary posting × skill matrix, TF-IDF weighted (IDF down-weights ubiquitous skills such as Communication).
k was searched over [6, 8, 10, 12, 14, 16]: NMF by mean UMass topic coherence of each topic's top-10 skills (higher is better),
KMeans by cosine silhouette on a 10,000-posting sample.

| k | nmf_umass_coherence | nmf_topic_diversity | nmf_recon_err | kmeans_silhouette_cosine | kmeans_inertia |
|---|---|---|---|---|---|
| 6 | -1.898 | 0.967 | 501.251 | 0.048 | 261601.219 |
| 8 | -1.951 | 0.912 | 495.097 | 0.041 | 257412.125 |
| 10 | -2.034 | 0.880 | 489.235 | 0.048 | 254510.656 |
| 12 | -2.089 | 0.800 | 484.003 | 0.048 | 250735.531 |
| 14 | -2.157 | 0.821 | 477.927 | 0.060 | 248523.094 |
| 16 | -2.205 | 0.769 | 472.527 | 0.061 | 245220.781 |

Selected: **NMF k=6** (best coherence), **KMeans k=16** (best silhouette).
**Note:** the selected k for NMF and KMeans sits on the edge of the search grid, i.e. the criterion is monotone over this range rather than peaking (coherence favours fewer topics, silhouette more clusters; a wider 4–24 grid on the pilot showed the same trend). The data do not single out a k; treat these as convenient resolutions, not as the 'true' number of skill profiles.
Silhouette values are low in absolute terms, which is expected for sparse, overlapping skill sets: postings do not
form well-separated clusters, so the profiles are best read as soft themes.

### NMF topics (k=6) — top 15 skills each

Size = postings whose largest topic weight is this topic.

- **topic 3** — 66,041 postings (22.0%); mostly Tech Engineering 24%, Skilled Trades Ops 23%, Other 19%
  - Workplace / OSHA Safety, Production, Manufacturing, Quality Assurance, Electrical Systems, Troubleshooting, Project Management, Repair, Process Improvement, Driving, Inspection, Software Development, Preventive Maintenance, Blueprints, Creativity
- **topic 2** — 56,044 postings (18.7%); mostly Other 26%, Management HR Admin 24%, Sales Customer 19%
  - Customer Service, Sanitation, Inventory Management, Merchandising, Scheduling, People Management, Workplace / OSHA Safety, Communication, Food Preparation, Retail / Store Operations, Retail Operations, Driving, Customer Focus, Cash Handling, Coaching
- **topic 4** — 55,652 postings (18.6%); mostly Other 25%, Management HR Admin 23%, Finance Accounting 15%
  - Microsoft Excel, Microsoft Office, Written Communication, Microsoft PowerPoint, Accounting, Microsoft Word, Microsoft Outlook, Presentation Skills, Marketing, Data Analysis, Computer Proficiency, Project Management, Budgeting, Financial Analysis, Forecasting
- **topic 1** — 48,240 postings (16.1%); mostly Healthcare Nursing 37%, Healthcare Clinical 21%, Other 13%
  - Nursing, Patient Care, BLS, ACLS, CPR, Medication Administration, Quality Improvement, Patient Education, Clinical Quality, Critical Care, Staffing, Care Planning, Clinical Skills, Critical Thinking, Infection Control
- **topic 0** — 40,794 postings (13.6%); mostly Other 26%, Management HR Admin 19%, Sales Customer 12%
  - Problem Solving, Teamwork, Communication, Attention to Detail, Time Management, Interpersonal Skills, Critical Thinking, Decision Making, Multitasking, Adaptability, Initiative, Customer Service, Creativity, Conflict Resolution, Integrity
- **topic 5** — 33,229 postings (11.1%); mostly Healthcare Clinical 31%, Other 20%, Management HR Admin 15%
  - Diagnosis, Mental Health, Assessment, Counseling, Professional Development, Psychology, Social Work, Case Management, Physical Therapy, Coaching, Internal Medicine, Teamwork, People Management, Confidentiality, Writing

### KMeans clusters (k=16) — top 15 skills by centroid weight

- **cluster 6** — 43,315 postings (14.4%); mostly Other 26%, Management HR Admin 19%, Healthcare Clinical 12%
  - Communication, Teamwork, Interpersonal Skills, Adaptability, Writing, Coaching, Problem Solving, Workplace / OSHA Safety, Professional Development, Microsoft Office, Assessment, Attention to Detail, Integrity, People Management, Written Communication
- **cluster 3** — 33,843 postings (11.3%); mostly Healthcare Nursing 34%, Healthcare Clinical 23%, Other 14%
  - Patient Care, Nursing, Teamwork, Diagnosis, Communication, Assessment, Quality Improvement, Clinical Quality, Patient Education, Medication Administration, Critical Thinking, Physical Therapy, Care Planning, Clinical Skills, Internal Medicine
- **cluster 1** — 29,143 postings (9.7%); mostly Other 30%, Management HR Admin 20%, Hospitality Food 15%
  - Customer Service, Communication, Teamwork, Attention to Detail, Sanitation, Problem Solving, Time Management, Food Preparation, Scheduling, Workplace / OSHA Safety, Multitasking, People Management, Microsoft Office, Cashiering, Food Service
- **cluster 7** — 19,919 postings (6.6%); mostly Other 28%, Management HR Admin 26%, Sales Customer 10%
  - Microsoft Excel, Microsoft Word, Microsoft PowerPoint, Microsoft Outlook, Microsoft Office, Attention to Detail, Communication, Teamwork, Written Communication, Customer Service, Time Management, Problem Solving, Computer Proficiency, Interpersonal Skills, Presentation Skills
- **cluster 8** — 19,572 postings (6.5%); mostly Other 26%, Management HR Admin 22%, Tech Engineering 19%
  - Project Management, Quality Assurance, Communication, Construction Management, Civil Engineering, Workplace / OSHA Safety, Budgeting, Teamwork, Scheduling, Problem Solving, Microsoft Office, Attention to Detail, AutoCAD, People Management, Risk Management
- **cluster 5** — 19,144 postings (6.4%); mostly Sales Customer 44%, Management HR Admin 20%, Other 19%
  - Marketing, Sales, CRM, Prospecting, Presentation Skills, Communication, Negotiation, Teamwork, Customer Service, Interpersonal Skills, Microsoft Office, Problem Solving, Time Management, Social Media, Written Communication
- **cluster 12** — 18,010 postings (6.0%); mostly Skilled Trades Ops 25%, Management HR Admin 22%, Tech Engineering 21%
  - Manufacturing, Production, Workplace / OSHA Safety, Process Improvement, Quality Assurance, Quality Control (Manufacturing), Communication, Problem Solving, Teamwork, Supply Chain, Lean / Six Sigma, Attention to Detail, Inspection, People Management, Sanitation
- **cluster 10** — 15,898 postings (5.3%); mostly Healthcare Nursing 39%, Healthcare Clinical 20%, Other 13%
  - BLS, Nursing, ACLS, Patient Care, Critical Care, Teamwork, CPR, Communication, Assessment, Diagnosis, Critical Thinking, Staffing, Quality Improvement, Radiology, Patient Education
- **cluster 9** — 15,895 postings (5.3%); mostly Finance Accounting 48%, Management HR Admin 20%, Other 19%
  - Accounting, Microsoft Excel, Financial Analysis, Attention to Detail, Financial Statements, Budgeting, Data Analysis, Communication, Critical Thinking, Auditing, Microsoft Office, Problem Solving, Forecasting, GAAP, Teamwork
- **cluster 2** — 14,962 postings (5.0%); mostly Tech Engineering 40%, Other 25%, Management HR Admin 12%
  - Software Development, Python, Computer Science, SQL, Java, Agile, AWS, Cybersecurity, JavaScript, Troubleshooting, Automation, Git, Teamwork, Architecture, Testing
- **cluster 4** — 14,430 postings (4.8%); mostly Skilled Trades Ops 27%, Other 24%, Management HR Admin 18%
  - Driving, Customer Service, Workplace / OSHA Safety, Communication, Teamwork, Problem Solving, Attention to Detail, Customer Focus, Repair, Sanitation, People Management, Microsoft Office, Transportation, Adaptability, Time Management
- **cluster 11** — 14,426 postings (4.8%); mostly Management HR Admin 32%, Sales Customer 30%, Other 22%
  - Merchandising, Customer Service, Inventory Management, Retail / Store Operations, Retail Operations, Communication, Problem Solving, Teamwork, Loss Prevention, Sanitation, Workplace / OSHA Safety, People Management, Attention to Detail, Cash Handling, Scheduling
- **cluster 15** — 14,143 postings (4.7%); mostly Skilled Trades Ops 43%, Tech Engineering 15%, Other 15%
  - Electrical Systems, Repair, Troubleshooting, Workplace / OSHA Safety, Preventive Maintenance, Blueprints, HVAC, Plumbing, Communication, Electrical Engineering, Equipment Operation, Driving, Teamwork, Problem Solving, Customer Service
- **cluster 13** — 12,078 postings (4.0%); mostly Healthcare Clinical 46%, Management HR Admin 14%, Other 13%
  - Mental Health, Counseling, Diagnosis, Psychology, Social Work, Case Management, Assessment, Teamwork, Communication, Nursing, Marriage and Family Therapy, Professional Development, Patient Care, Physical Therapy, Internal Medicine
- **cluster 0** — 8,827 postings (2.9%); mostly Other 22%, Healthcare Nursing 19%, Healthcare Clinical 18%
  - CPR, First Aid, Workplace / OSHA Safety, Nursing, Communication, Patient Care, Teamwork, Customer Service, Sanitation, Assessment, Driving, Diagnosis, Interpersonal Skills, People Management, Problem Solving
- **cluster 14** — 6,395 postings (2.1%); mostly Tech Engineering 36%, Other 23%, Management HR Admin 13%
  - Architecture, Project Management, AutoCAD, Teamwork, Revit, Communication, Cybersecurity, Software Development, Computer Science, Problem Solving, Creativity, Presentation Skills, Electrical Engineering, Troubleshooting, Electrical Systems

## (b) Predicting occupation group from the skill set

Multinomial logistic regression (TF-IDF features, `class_weight="balanced"`, C=1.0) on 12 groups
(excluding the catch-all `Other`), stratified 188,352 train / 47,088 test.
The label `position_group` comes from LinkedIn's `search_position`, not from the description, so the target is
independent of the extracted skills.

| metric | logistic regression | majority-class baseline |
|---|---|---|
| accuracy | **0.463** | 0.234 |
| macro-F1 | **0.444** | 0.032 |
| weighted-F1 | 0.445 | — |

### Per-class test performance

| position_group | precision | recall | f1 | support |
|---|---|---|---|---|
| Healthcare_Nursing | 0.556 | 0.856 | 0.674 | 4432 |
| Healthcare_Clinical | 0.613 | 0.597 | 0.605 | 5332 |
| Finance_Accounting | 0.512 | 0.698 | 0.591 | 2655 |
| Tech_Engineering | 0.547 | 0.555 | 0.551 | 4569 |
| Sales_Customer | 0.582 | 0.499 | 0.537 | 6049 |
| Hospitality_Food | 0.354 | 0.785 | 0.488 | 1389 |
| Skilled_Trades_Ops | 0.541 | 0.401 | 0.461 | 6813 |
| Legal_Compliance | 0.274 | 0.831 | 0.412 | 551 |
| Science_Research | 0.218 | 0.657 | 0.327 | 712 |
| Education | 0.237 | 0.317 | 0.272 | 2610 |
| Creative_Media | 0.132 | 0.473 | 0.206 | 945 |
| Management_HR_Admin | 0.498 | 0.127 | 0.202 | 11031 |

### 10 most important skills per group (largest positive coefficients)

- **Management HR Admin**: Sales, Merchandising, Restaurant Management, People Management, Oncology, Administrative Support, Employee Relations, Content Marketing, Case Management, SEO
- **Skilled Trades Ops**: Blueprints, Phlebotomy, Repair, Construction Management, Civil Engineering, Inspection, Testing, Electrical Systems, Welding, Driving
- **Sales Customer**: Sales, Cashiering, Retail / Store Operations, CRM, Loss Prevention, Prospecting, ACLS, Customer Service, Merchandising, SaaS
- **Healthcare Clinical**: Marriage and Family Therapy, Radiology, Patient Care, Dental Hygiene, Child Development, Internal Medicine, Curriculum Development, Mental Health, Counseling, Surgery
- **Tech Engineering**: Testing, Civil Engineering, Mechanical Engineering, AutoCAD, Architecture, Revit, SolidWorks, Manufacturing, C#, AWS
- **Healthcare Nursing**: Nursing, Patient Care, Care Planning, Medication Administration, Critical Care, Pediatrics, CPR, Internal Medicine, Infection Control, Patient Education
- **Finance Accounting**: Accounting, GAAP, Benefits Administration, Auditing, Employee Relations, Financial Statements, Accounts Payable, Payroll, Litigation, Variance Analysis
- **Education**: Curriculum Development, Child Development, Planogram, CPR, Clinical Training, Assessment, Psychology, First Aid, SaaS, Statistics
- **Hospitality Food**: Food Preparation, Restaurant Management, Food Service, Sanitation, Food Safety, Hospitality, Customer Service, POS Systems, SQL, Jenkins
- **Creative Media**: Content Marketing, Architecture, Electrical Engineering, AutoCAD, Electrical Systems, Production, Prototyping, Merchandising, Project Management, MATLAB
- **Science Research**: Clinical Analysis, Chemistry, Data Analysis, Instrumentation, Troubleshooting, Quality Assurance, Oncology, Data Science, Product Development, Docker
- **Legal Compliance**: Litigation, Negotiation, Case Management, Filing, Real Estate Development, Advocacy, Electrical Engineering, Writing, Critical Thinking, Fund Management

### Most frequent confusions (true → predicted, test set)

| true | predicted | n |
|---|---|---|
| Management_HR_Admin | Skilled_Trades_Ops | 1213 |
| Management_HR_Admin | Sales_Customer | 1204 |
| Management_HR_Admin | Education | 1012 |
| Management_HR_Admin | Finance_Accounting | 1004 |
| Management_HR_Admin | Hospitality_Food | 997 |
| Management_HR_Admin | Creative_Media | 950 |
| Healthcare_Clinical | Healthcare_Nursing | 947 |
| Management_HR_Admin | Healthcare_Nursing | 945 |

## Caveats

- Postings come from LinkedIn searches in four English-speaking countries in early 2024; they are not a random sample of the labour market.
- `position_group` is a coarse mapping of 1,993 search positions; `Management_HR_Admin` in particular is heterogeneous, which caps accuracy.
- Coefficients show association with a group relative to the others, not importance of the skill in absolute demand.
