"""
Controlled vocabulary + noise rules for skill / qualification extraction (v2).

Changes vs v1 (Claude review):
- KEEP_RE whitelist so noise rules don't kill real skills
- tighter degree / benefit noise patterns
- AMBIGUOUS_FOR_SUMMARY: only match these in job_skills NER tokens, not JD text
- canonical names are NOT auto-added as summary keywords (aliases only, explicit)
- much larger seed skill vocabulary
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Noise tokens (look like skills after split(',') but shouldn't enter dashboard)
# ---------------------------------------------------------------------------
NOT_A_SKILL_PATTERNS = [
    # education / years — be specific so "Scrum Master" / "Master Data" survive
    r"\bhigh school\b",
    r"\bged\b",
    r"\bbachelor'?s?(?:\s+degree)?\b",
    r"\bmaster'?s?\s+degree\b",
    r"\bmasters?\s+degree\b",
    r"\bmba\b",
    r"\bph\.?\s?d\b",
    r"\bassociate'?s?\s+degree\b",
    r"\bcollege degree\b",
    r"\bundergraduate degree\b",
    r"\byears? of experience\b",
    r"\b\d{1,2}\+?\s*years?\b",
    # soft requirements / physical / scheduling that aren't teachable skills
    r"\bability to\b",
    r"\bwilling(?:ness)? to\b",
    r"\bmust be able\b",
    r"\blift(?:ing)?\b",
    r"\bpounds?\b",
    r"\blbs\.?\b",
    r"\bstand for\b",
    r"\bwalk for\b",
    r"\bphysical (?:stamina|strength|fitness)\b",
    r"\bstanding\b",
    r"\bwalking\b",
    r"\bbending\b",
    r"\bkneeling\b",
    r"\breaching\b",
    r"\bstooping\b",
    r"\bclimbing\b",
    r"\bweekend",
    r"\bholidays?\b",
    r"\bflexible (?:hours|schedule|work schedule)\b",
    r"\bindependent work\b",
    r"\breliable transportation\b",
    r"\btravel\b",
    # employer boilerplate / benefits
    r"\bequal opportunity\b",
    r"\beeo\b",
    r"\b401\s*\(?\s*k\)?",
    r"\bpto\b",
    r"\bpaid (?:time off|vacation)\b",
    r"\btuition reimbursement\b",
    r"\bemployee assistance program\b",
    r"\bweekly pay\b",
    r"\bhealth insurance\b",
    r"\bmedical insurance\b",
    r"\blife insurance\b",
    r"\bdisability insurance\b",
    r"\bdental insurance\b",
    r"\bvision insurance\b",
    r"\bdental benefits\b",
    r"\bvision benefits\b",
    r"\bpet insurance\b",
    r"\bmalpractice insurance\b",
    r"\bflexible spending accounts?\b",
    r"\bidentity theft protection\b",
    r"\bcompetitive (?:salary|compensation|pay|wages)\b",
    r"\breferral bonus(?:es)?\b",
    r"\bemployee discounts?\b",
    r"\brelocation assistance\b",
    r"\bretirement plan\b",
    r"\bparental leave\b",
    r"\bpaid parental leave\b",
    r"\bworklife balance\b",
    r"\bwork[- ]life balance\b",
    r"\bremote work\b",
    r"\bshift work\b",
    r"\bteam environment\b",
    r"\bpositive attitude\b",
    r"\bstrong work ethic\b",
    r"\bwork ethic\b",
    r"\bpunctuality\b",
    r"\bdependability\b",
    r"\bregular attendance\b",
    r"\battendance\b",
    r"\bphysical (?:demands|requirements|ability)\b",
    r"\bmanual dexterity\b",
    r"\bvisual acuity\b",
    r"\bsitting\b",
    r"\bpushing\b",
    r"\bpulling\b",
    r"\bcarrying\b",
    r"\bcovid[- ]?19 vaccination\b",
    r"\bdrug screening\b",
    r"\bu\.?s\.? citizenship\b",
    r"\bus citizenship\b",
    r"\bequal employment opportunity\b",
    r"\bperks?\b",
    r"\bbenefits\b",
    # licenses as free-text noise (structured certs handled separately)
    r"\bdriver'?s? license\b",
    r"\bdriving license\b",
    r"\bvalid license\b",
    r"\brn license\b",
    r"\bbarber license\b",
    r"\bcosmetology license\b",
    r"\bwork authorization\b",
    r"\bus citizen\b",
    r"\bbackground check\b",
    r"\bdrug (?:test|screen)\b",
    r"\bfast[- ]?paced environment\b",
]

NOT_A_SKILL_RE = re.compile("|".join(f"(?:{p})" for p in NOT_A_SKILL_PATTERNS), re.I)

# Real skills that would otherwise trip noise rules
KEEP_RE = re.compile(
    r"(?i)scrum master|master data|dental hygien|computer vision|"
    r"benefits admin|high availability|vision care|machine vision|"
    r"employee relations|employee training"
)

# Ambiguous single words / short labels — OK to match against NER skill tokens
# (usually already skill-like), but DO NOT match against JD requirement text.
# Only skills that exist in SKILL_DICT (16 names not in vocab were dropped)
AMBIGUOUS_FOR_SUMMARY = {
    "Organization",
    "Training",
    "Leadership",
    "Sales",
    "React",
    "Agile",
    "Docker",
    "Safety",
    "Documentation",
    "Research",
    "Security",
    "Development",
    "Writing",
    "Assessment",
    "Project Coordination",
    "Teaching",
    "Driving",
    "Testing",
    "Design",
    "Management",
    "Engineering",
    "Healthcare",
    "Hospitality",
    "Motivation",
    "Integrity",
    "Empathy",
    "Patience",
    "Creativity",
    "Reliability",
    "Initiative",
    "Coaching",
    "Hiring",
    "Reporting",
    "Compliance",
    "Analysis",
    "Quality",
    "Procedures",
    "Equity",
    "Insurance",
    "Operations",
    "Production",
    "Business Administration",
    "Information Technology",
    "Windows",
    "Monitoring",
    "Implementation",
    "Repair",
    "Delegation",
    "Staffing",
    "Advocacy",
    "Spanish",
    "Bilingual",
    "Dentistry",
    "Surgery",
    "Diagnosis",
    "Psychology",
}

# ---------------------------------------------------------------------------
# Skill vocabulary (canonical -> aliases, type, course_domain)
# ---------------------------------------------------------------------------
SKILL_META = {
    # soft
    "Communication": {"aliases": [
        "communication skills", "verbal communication", "communication",
        "strong communication", "excellent communication", "written and verbal communication",
        "oral communication", "oral and written communication",
        "communicate clearly", "effectively communicate", "communicate verbally",
        "communicate in writing", "professional communication",
    ], "type": "soft", "domain": "Professional Skills"},
    "Written Communication": {"aliases": [
        "written communication", "written communications", "written and oral",
        "strong oral and written", "oral and written communication skills",
    ], "type": "soft", "domain": "Professional Skills"},
    "Teamwork": {"aliases": [
        "teamwork", "team work", "team player", "collaboration", "collaborative",
        "work as a team", "works well with others", "ability to work in a team",
        "team environment", "collaborate effectively", "work collaboratively",
        "ability to work collaboratively", "teaming skills",
    ], "type": "soft", "domain": "Professional Skills"},
    "Leadership": {"aliases": [
        "leadership", "team leadership", "people leadership", "leading teams",
        "leadership skills", "lead a team", "lead teams", "demonstrated leadership",
        "leadership experience", "provide leadership",
    ], "type": "soft", "domain": "Management"},
    "Problem Solving": {"aliases": ["problem solving", "problemsolving", "problem-solving"], "type": "soft", "domain": "Professional Skills"},
    "Time Management": {"aliases": ["time management", "time-management", "prioritization", "prioritising"], "type": "soft", "domain": "Professional Skills"},
    "Attention to Detail": {"aliases": ["attention to detail", "detail oriented", "detail-oriented", "detailoriented", "detail orientation", "accuracy"], "type": "soft", "domain": "Professional Skills"},
    "Customer Service": {"aliases": ["customer service", "customer support", "client service", "guest service"], "type": "soft", "domain": "Sales & Customer Success"},
    "Adaptability": {"aliases": ["adaptability", "flexibility", "adaptable"], "type": "soft", "domain": "Professional Skills"},
    "Interpersonal Skills": {"aliases": ["interpersonal skills", "people skills", "relationship building", "client relations"], "type": "soft", "domain": "Professional Skills"},
    "Organization": {"aliases": ["organization", "organizational skills", "organisational skills"], "type": "soft", "domain": "Professional Skills"},
    "Multitasking": {"aliases": ["multitasking", "multi-tasking", "multi tasking"], "type": "soft", "domain": "Professional Skills"},
    "Critical Thinking": {"aliases": ["critical thinking", "critical-thinking", "analytical skills", "analytical thinking"], "type": "soft", "domain": "Professional Skills"},
    "Presentation Skills": {"aliases": ["presentation skills", "public speaking", "presentations"], "type": "soft", "domain": "Professional Skills"},
    "Negotiation": {"aliases": ["negotiation", "negotiating"], "type": "soft", "domain": "Sales & Customer Success"},
    "Conflict Resolution": {"aliases": ["conflict resolution", "conflict management"], "type": "soft", "domain": "Professional Skills"},
    "Decision Making": {"aliases": ["decision making", "decisionmaking", "decision-making"], "type": "soft", "domain": "Professional Skills"},
    "Active Listening": {"aliases": ["active listening"], "type": "soft", "domain": "Professional Skills"},
    "Professionalism": {"aliases": ["professionalism"], "type": "soft", "domain": "Professional Skills"},
    "Initiative": {"aliases": ["initiative", "selfmotivation", "self-motivation", "self motivation", "selfstarter", "self-starter", "self starter"], "type": "soft", "domain": "Professional Skills"},
    "Empathy": {"aliases": ["empathy", "compassion"], "type": "soft", "domain": "Professional Skills"},
    "Stress Management": {"aliases": ["stress management"], "type": "soft", "domain": "Professional Skills"},
    "Team Building": {"aliases": ["team building"], "type": "soft", "domain": "Management"},
    "Motivation": {"aliases": ["motivation"], "type": "soft", "domain": "Professional Skills"},
    "Integrity": {"aliases": ["integrity", "ethics"], "type": "soft", "domain": "Professional Skills"},
    "Creativity": {"aliases": ["creativity", "innovation"], "type": "soft", "domain": "Professional Skills"},
    "Reliability": {"aliases": ["reliability"], "type": "soft", "domain": "Professional Skills"},
    "Patience": {"aliases": ["patience"], "type": "soft", "domain": "Professional Skills"},
    "Confidentiality": {"aliases": ["confidentiality"], "type": "soft", "domain": "Professional Skills"},
    "Diversity and Inclusion": {"aliases": ["diversity and inclusion"], "type": "soft", "domain": "Professional Skills"},
    "English Proficiency": {"aliases": ["english proficiency", "fluent in english", "proficient in english"], "type": "soft", "domain": "Professional Skills"},
    "Writing": {"aliases": ["writing", "report writing", "technical writing"], "type": "soft", "domain": "Professional Skills"},
    # office / tools
    "Microsoft Excel": {"aliases": ["excel", "ms excel", "microsoft excel", "spreadsheets"], "type": "tool", "domain": "Data & Analytics"},
    "Microsoft Office": {"aliases": ["microsoft office", "ms office", "microsoft office suite", "office 365", "microsoft 365"], "type": "tool", "domain": "Professional Skills"},
    "Microsoft Word": {"aliases": ["microsoft word", "ms word", "word"], "type": "tool", "domain": "Professional Skills"},
    "Microsoft PowerPoint": {"aliases": ["powerpoint", "ms powerpoint", "power point", "microsoft powerpoint"], "type": "tool", "domain": "Professional Skills"},
    "Microsoft Outlook": {"aliases": ["outlook", "ms outlook", "microsoft outlook"], "type": "tool", "domain": "Professional Skills"},
    "Microsoft Teams": {"aliases": ["microsoft teams", "ms teams"], "type": "tool", "domain": "Professional Skills"},
    "Microsoft Access": {"aliases": ["microsoft access", "ms access"], "type": "tool", "domain": "Professional Skills"},
    "OneDrive": {"aliases": ["onedrive", "one drive"], "type": "tool", "domain": "Professional Skills"},
    "Google Workspace": {"aliases": ["google workspace", "g suite", "google suite", "google docs", "google sheets"], "type": "tool", "domain": "Professional Skills"},
    "CMMS": {"aliases": ["cmms", "computerized maintenance management"], "type": "tool", "domain": "Operations"},
    "Preventive Maintenance": {"aliases": ["preventive maintenance", "preventative maintenance", "pm program"], "type": "hard", "domain": "Operations"},
    "Lean / Six Sigma": {"aliases": ["lean six sigma", "six sigma", "lean manufacturing", "lean methodology"], "type": "hard", "domain": "Operations"},
    "Requirements Gathering": {"aliases": ["requirements gathering", "gathering requirements", "requirements elicitation", "functional specifications"], "type": "hard", "domain": "Management"},
    "Planogram": {"aliases": ["planogram", "planograms"], "type": "hard", "domain": "Sales & Customer Success"},
    "Computer Literacy": {"aliases": ["computer literacy", "computer skills"], "type": "tool", "domain": "Professional Skills"},
    "Data Entry": {"aliases": ["data entry", "data collection", "record keeping"], "type": "tool", "domain": "Professional Skills"},
    "Salesforce": {"aliases": ["salesforce", "salesforce crm", "sfdc"], "type": "tool", "domain": "Sales & Customer Success"},
    "SAP": {"aliases": ["sap"], "type": "tool", "domain": "Operations"},
    "AutoCAD": {"aliases": ["autocad", "auto cad"], "type": "tool", "domain": "Engineering & Construction"},
    "Revit": {"aliases": ["revit", "autodesk revit"], "type": "tool", "domain": "Engineering & Construction"},
    "Tableau": {"aliases": ["tableau", "tableau desktop"], "type": "tool", "domain": "Data & Analytics"},
    "Power BI": {"aliases": ["power bi", "powerbi", "microsoft power bi"], "type": "tool", "domain": "Data & Analytics"},
    # data / tech
    "SQL": {"aliases": ["sql", "mysql", "postgresql", "postgres", "sql server", "t-sql"], "type": "hard", "domain": "Data & Analytics"},
    "Python": {"aliases": ["python", "python3", "python 3"], "type": "hard", "domain": "Data & Analytics"},
    "R Programming": {"aliases": ["r programming", "r language", "r studio", "rstudio"], "type": "hard", "domain": "Data & Analytics"},
    "Data Analysis": {"aliases": ["data analysis", "data analytics", "analyzing data"], "type": "hard", "domain": "Data & Analytics"},
    "Data Visualization": {"aliases": ["data visualization", "data viz"], "type": "hard", "domain": "Data & Analytics"},
    "Machine Learning": {"aliases": ["machine learning", "machine-learning"], "type": "hard", "domain": "Data & Analytics"},
    "Statistics": {"aliases": ["statistics", "statistical analysis"], "type": "hard", "domain": "Data & Analytics"},
    "ETL": {"aliases": ["etl", "data pipeline", "data pipelines", "data warehousing"], "type": "hard", "domain": "Data & Analytics"},
    "Reporting": {"aliases": [
        "reporting", "financial reporting", "write reports", "writing reports",
        "prepare reports", "preparing reports", "incident reports", "status reports",
        "management reports", "accident reports", "store reports", "report writing",
        "prepare and submit reports", "accurate store reports",
        "prepares various management reports", "department reports",
        "analyzing and reporting", "summarize presentations, reports",
        "timely and accurate store reports", "related reports",
    ], "type": "hard", "domain": "Data & Analytics"},
    "Forecasting": {"aliases": ["forecasting"], "type": "hard", "domain": "Data & Analytics"},
    "Software Development": {"aliases": ["software development", "software engineering", "programming"], "type": "hard", "domain": "Cloud & IT"},
    "Java": {"aliases": ["java", "core java"], "type": "hard", "domain": "Cloud & IT"},
    "JavaScript": {"aliases": ["javascript", "node.js", "nodejs"], "type": "hard", "domain": "Cloud & IT"},
    "React": {"aliases": ["react", "react.js", "reactjs"], "type": "hard", "domain": "Cloud & IT"},
    "AWS": {"aliases": ["aws", "amazon web services"], "type": "hard", "domain": "Cloud & IT"},
    "Azure": {"aliases": ["azure", "microsoft azure"], "type": "hard", "domain": "Cloud & IT"},
    "Google Cloud": {"aliases": ["google cloud", "gcp", "google cloud platform"], "type": "hard", "domain": "Cloud & IT"},
    "Docker": {"aliases": ["docker", "docker containers"], "type": "hard", "domain": "Cloud & IT"},
    "Kubernetes": {"aliases": ["kubernetes", "k8s"], "type": "hard", "domain": "Cloud & IT"},
    "Linux": {"aliases": ["linux", "unix"], "type": "hard", "domain": "Cloud & IT"},
    "Git": {"aliases": ["git", "github", "gitlab"], "type": "tool", "domain": "Cloud & IT"},
    "Version Control": {"aliases": ["version control", "source control"], "type": "tool", "domain": "Cloud & IT"},
    "Cybersecurity": {"aliases": ["cybersecurity", "information security", "infosec", "network security"], "type": "hard", "domain": "Cloud & IT"},
    "Networking": {"aliases": ["networking", "network administration", "tcp/ip"], "type": "hard", "domain": "Cloud & IT"},
    "Troubleshooting": {"aliases": ["troubleshooting", "technical troubleshooting", "debugging"], "type": "hard", "domain": "Cloud & IT"},
    "Automation": {"aliases": ["automation"], "type": "hard", "domain": "Cloud & IT"},
    "High Availability": {"aliases": ["high availability"], "type": "hard", "domain": "Cloud & IT"},
    "Computer Vision": {"aliases": ["computer vision", "machine vision"], "type": "hard", "domain": "Data & Analytics"},
    "Computer Science": {"aliases": ["computer science"], "type": "hard", "domain": "Cloud & IT"},
    "Testing": {"aliases": ["qa testing", "software testing", "test automation"], "type": "hard", "domain": "Cloud & IT"},
    "Security": {"aliases": ["security"], "type": "hard", "domain": "Cloud & IT"},
    # management / business
    "Project Management": {"aliases": ["project management", "managing projects"], "type": "hard", "domain": "Management"},
    "Agile": {"aliases": ["agile", "agile methodology", "agile methodologies", "agile development", "scrum", "kanban"], "type": "hard", "domain": "Management"},
    "Scrum Master": {"aliases": ["scrum master"], "type": "hard", "domain": "Management"},
    "Product Management": {"aliases": ["product management", "product owner"], "type": "hard", "domain": "Management"},
    "Budgeting": {"aliases": ["budgeting", "budget management"], "type": "hard", "domain": "Management"},
    "Strategic Planning": {"aliases": ["strategic planning"], "type": "hard", "domain": "Management"},
    "Change Management": {"aliases": ["change management"], "type": "hard", "domain": "Management"},
    "Performance Management": {"aliases": ["performance management"], "type": "hard", "domain": "Management"},
    # People Management is the canonical name (gold); Team Management merges into it.
    "People Management": {"aliases": [
        "people management", "team management", "supervisory experience",
        "supervision of staff", "managing staff", "manage a team", "supervise staff",
        "staff supervision", "direct reports", "supervisory responsibilities",
        "manage the team", "leading a team of", "supervise a team",
    ], "type": "hard", "domain": "Management"},
    "Team Management": {"aliases": ["team management", "supervisory experience", "supervision"], "type": "hard", "domain": "Management"},
    "Coaching": {"aliases": ["coaching", "mentoring"], "type": "hard", "domain": "Management"},
    "Hiring": {"aliases": ["hiring", "recruiting", "talent acquisition"], "type": "hard", "domain": "Management"},
    "Human Resources": {"aliases": ["human resources", "hr"], "type": "hard", "domain": "Management"},
    "Benefits Administration": {"aliases": ["benefits administration", "benefits admin"], "type": "hard", "domain": "Management"},
    "Training": {"aliases": ["training", "employee training", "staff training", "training delivery"], "type": "hard", "domain": "Management"},
    "Scheduling": {"aliases": ["scheduling", "staff scheduling"], "type": "hard", "domain": "Management"},
    "Process Improvement": {"aliases": ["process improvement", "continuous improvement"], "type": "hard", "domain": "Operations"},
    "Risk Management": {"aliases": ["risk management", "risk assessment"], "type": "hard", "domain": "Management"},
    "Compliance": {"aliases": ["compliance", "regulatory compliance"], "type": "hard", "domain": "Operations"},
    "Management": {"aliases": ["management", "people management", "general management"], "type": "hard", "domain": "Management"},
    # finance
    "Accounting": {"aliases": ["accounting", "bookkeeping", "financial accounting"], "type": "hard", "domain": "Finance & Accounting"},
    "Financial Analysis": {"aliases": ["financial analysis", "fp&a"], "type": "hard", "domain": "Finance & Accounting"},
    "Financial Modeling": {"aliases": ["financial modeling", "financial modelling"], "type": "hard", "domain": "Finance & Accounting"},
    "Financial Management": {"aliases": ["financial management"], "type": "hard", "domain": "Finance & Accounting"},
    "Payroll": {"aliases": ["payroll"], "type": "hard", "domain": "Finance & Accounting"},
    "Cash Handling": {"aliases": ["cash handling"], "type": "hard", "domain": "Finance & Accounting"},
    # sales / marketing
    "Sales": {"aliases": ["sales", "selling", "business development", "b2b sales"], "type": "hard", "domain": "Sales & Customer Success"},
    "CRM": {"aliases": ["crm", "customer relationship management"], "type": "tool", "domain": "Sales & Customer Success"},
    "Merchandising": {"aliases": ["merchandising", "merchandise handling", "product knowledge"], "type": "hard", "domain": "Sales & Customer Success"},
    "Retail Operations": {"aliases": ["retail experience", "retail operations"], "type": "hard", "domain": "Sales & Customer Success"},
    "Marketing": {"aliases": ["marketing", "digital marketing", "marketing strategy"], "type": "hard", "domain": "Marketing"},
    "SEO": {"aliases": ["seo", "search engine optimization"], "type": "hard", "domain": "Marketing"},
    "Content Marketing": {"aliases": ["content marketing", "content strategy", "content creation"], "type": "hard", "domain": "Marketing"},
    "Event Planning": {"aliases": ["event planning"], "type": "hard", "domain": "Marketing"},
    # operations
    "Inventory Management": {"aliases": ["inventory management", "inventory control", "stock management"], "type": "hard", "domain": "Operations"},
    "Supply Chain": {"aliases": ["supply chain", "supply chain management", "logistics"], "type": "hard", "domain": "Operations"},
    "Quality Assurance": {"aliases": ["quality assurance", "quality control", "qa"], "type": "hard", "domain": "Operations"},
    "Equipment Maintenance": {"aliases": ["equipment maintenance"], "type": "hard", "domain": "Operations"},
    "Manufacturing": {"aliases": ["manufacturing"], "type": "hard", "domain": "Operations"},
    "HVAC": {"aliases": ["hvac"], "type": "hard", "domain": "Operations"},
    "Sanitation": {"aliases": ["sanitation", "cleaning", "housekeeping", "cleanliness", "hygiene"], "type": "hard", "domain": "Operations"},
    "Food Preparation": {"aliases": ["food preparation", "food handling", "cooking"], "type": "hard", "domain": "Operations"},
    "Restaurant Management": {"aliases": ["restaurant management"], "type": "hard", "domain": "Operations"},
    "Hospitality": {"aliases": ["hospitality"], "type": "hard", "domain": "Operations"},
    "Safety": {"aliases": [
        "safety", "workplace safety", "osha", "osha safety", "safety protocols",
        "safety procedures", "safe work practices", "health and safety",
        "safety standards", "safety regulations", "ehs", "environmental health and safety",
        "safe workplace", "work safely", "safety practices",
    ], "type": "hard", "domain": "Operations"},
    "Driving": {"aliases": [
        "driving", "valid driver's license", "valid drivers license", "driver's license required",
        "drivers license required", "drive company vehicle", "driving record",
        "ability to drive", "must drive", "reliable vehicle", "operate a vehicle",
        "driving licence", "drive and operate", "clean driving licence",
        "operate motor vehicle", "operate a motor vehicle", "company vehicles",
        "valid florida driver's license", "type of vehicle being driven",
    ], "type": "hard", "domain": "Operations"},
    "Administrative Support": {"aliases": ["administrative support"], "type": "hard", "domain": "Professional Skills"},
    # engineering / construction
    "Civil Engineering": {"aliases": ["civil engineering"], "type": "hard", "domain": "Engineering & Construction"},
    "Mechanical Engineering": {"aliases": ["mechanical engineering"], "type": "hard", "domain": "Engineering & Construction"},
    "Electrical Engineering": {"aliases": ["electrical engineering"], "type": "hard", "domain": "Engineering & Construction"},
    "Construction Management": {"aliases": ["construction management"], "type": "hard", "domain": "Engineering & Construction"},
    "Architecture": {"aliases": ["architecture"], "type": "hard", "domain": "Engineering & Construction"},
    "Engineering": {"aliases": ["engineering"], "type": "hard", "domain": "Engineering & Construction"},
    "Design": {"aliases": ["design"], "type": "hard", "domain": "Engineering & Construction"},
    "Master Data Management": {"aliases": ["master data", "master data management"], "type": "hard", "domain": "Data & Analytics"},
    # healthcare
    "Nursing": {"aliases": ["nursing", "registered nurse", "clinical nursing"], "type": "hard", "domain": "Healthcare & Nursing"},
    "Patient Care": {"aliases": ["patient care", "direct patient care", "patient assessment"], "type": "hard", "domain": "Healthcare & Nursing"},
    "Patient Education": {"aliases": ["patient education"], "type": "hard", "domain": "Healthcare & Nursing"},
    "Electronic Health Records": {"aliases": ["electronic health records", "ehr", "emr", "epic", "epic systems", "cerner"], "type": "tool", "domain": "Healthcare & Nursing"},
    "Medication Administration": {"aliases": ["medication administration", "med administration", "medication management"], "type": "hard", "domain": "Healthcare & Nursing"},
    "Vital Signs": {"aliases": ["vital signs", "taking vital signs", "patient vitals"], "type": "hard", "domain": "Healthcare & Nursing"},
    "Care Planning": {"aliases": ["care planning", "nursing care plan", "care plans"], "type": "hard", "domain": "Healthcare & Nursing"},
    "Case Management": {"aliases": ["case management"], "type": "hard", "domain": "Healthcare & Nursing"},
    "Medical Terminology": {"aliases": ["medical terminology"], "type": "hard", "domain": "Healthcare & Nursing"},
    "HIPAA": {"aliases": ["hipaa", "hipaa compliance", "patient privacy"], "type": "hard", "domain": "Healthcare & Nursing"},
    "CPR": {"aliases": ["cpr", "cardiopulmonary resuscitation"], "type": "certification", "domain": "Healthcare & Nursing"},
    "BLS": {"aliases": ["bls", "basic life support", "bls certification", "bls certified"], "type": "certification", "domain": "Healthcare & Nursing"},
    "ACLS": {"aliases": ["acls", "advanced cardiac life support"], "type": "certification", "domain": "Healthcare & Nursing"},
    "Documentation": {"aliases": [
        "documentation", "clinical documentation", "charting", "medical documentation",
        "documenting", "maintain records", "maintaining records", "keep records",
        "write incident reports", "accurate documentation", "document all",
        "proper documentation", "complete documentation", "timely documentation",
        "document and maintain", "maintain accurate records", "record keeping",
        "quality planning documentation", "maintain documentation",
        "paperwork and documentation", "required paperwork and documentation",
        "documented certification records",
    ], "type": "hard", "domain": "Healthcare & Nursing"},
    "Healthcare": {"aliases": ["healthcare", "medical"], "type": "hard", "domain": "Healthcare & Nursing"},
    "Counseling": {"aliases": ["counseling", "counselling"], "type": "hard", "domain": "Healthcare & Nursing"},
    "Dental Hygiene": {"aliases": ["dental hygiene", "dental hygienist"], "type": "hard", "domain": "Healthcare & Nursing"},
    "Chemistry": {"aliases": ["chemistry"], "type": "hard", "domain": "Healthcare & Nursing"},
    "Research": {"aliases": ["research", "legal research"], "type": "hard", "domain": "Professional Skills"},
    "Teaching": {"aliases": ["teaching", "patient education", "staff teaching"], "type": "hard", "domain": "Professional Skills"},
    "Assessment": {"aliases": ["assessment", "evaluation"], "type": "hard", "domain": "Professional Skills"},
    "Litigation": {"aliases": ["litigation"], "type": "hard", "domain": "Professional Skills"},
    "Mathematical Calculations": {"aliases": ["mathematical calculations", "math skills", "mathematics", "mathematical skills"], "type": "hard", "domain": "Professional Skills"},
}

# Expansion from unmapped high-frequency NER tokens (sample + 200k audit)
SKILL_META_ROUND2 = {
    # soft / professional
    "Accountability": {"aliases": ["accountability"], "type": "soft", "domain": "Professional Skills"},
    "Strategic Thinking": {"aliases": ["strategic thinking"], "type": "soft", "domain": "Management"},
    "Customer Focus": {"aliases": ["customer focus", "customer satisfaction", "customer relations"], "type": "soft", "domain": "Sales & Customer Success"},
    "Resilience": {"aliases": ["resilience"], "type": "soft", "domain": "Professional Skills"},
    "Creative Thinking": {"aliases": ["creative thinking"], "type": "soft", "domain": "Professional Skills"},
    "Goal Setting": {"aliases": ["goal setting"], "type": "soft", "domain": "Professional Skills"},
    "Stakeholder Engagement": {"aliases": ["stakeholder engagement"], "type": "soft", "domain": "Management"},
    "Bilingual": {"aliases": ["bilingual"], "type": "soft", "domain": "Professional Skills"},
    "Spanish": {"aliases": ["spanish"], "type": "soft", "domain": "Professional Skills"},
    # sales
    "Prospecting": {"aliases": ["prospecting", "lead generation", "cold calling"], "type": "hard", "domain": "Sales & Customer Success"},
    "Client Relationships": {"aliases": ["client relationships"], "type": "soft", "domain": "Sales & Customer Success"},
    "Pricing": {"aliases": ["pricing"], "type": "hard", "domain": "Sales & Customer Success"},
    "POS Systems": {"aliases": ["pos systems", "cash register operation"], "type": "tool", "domain": "Sales & Customer Success"},
    "Social Media": {"aliases": ["social media"], "type": "hard", "domain": "Marketing"},
    "Public Relations": {"aliases": ["public relations"], "type": "hard", "domain": "Marketing"},
    # management / HR / ops
    "Recruitment": {"aliases": ["recruitment", "interviewing", "onboarding"], "type": "hard", "domain": "Management"},
    "Employee Relations": {"aliases": ["employee relations"], "type": "hard", "domain": "Management"},
    "Delegation": {"aliases": ["delegation"], "type": "hard", "domain": "Management"},
    "Staffing": {"aliases": ["staffing"], "type": "hard", "domain": "Management"},
    "Staff Development": {"aliases": ["staff development", "team development", "mentorship"], "type": "hard", "domain": "Management"},
    "Policy Development": {"aliases": ["policy development"], "type": "hard", "domain": "Management"},
    "Business Administration": {"aliases": ["business administration"], "type": "hard", "domain": "Management"},
    "Business Acumen": {"aliases": ["business acumen"], "type": "hard", "domain": "Management"},
    "Business Analysis": {"aliases": ["business analysis", "requirements gathering"], "type": "hard", "domain": "Management"},
    "Operations": {"aliases": ["operations", "store operations"], "type": "hard", "domain": "Operations"},
    "Cost Control": {"aliases": ["cost control"], "type": "hard", "domain": "Operations"},
    "Loss Prevention": {"aliases": ["loss prevention"], "type": "hard", "domain": "Operations"},
    "Procurement": {"aliases": ["procurement"], "type": "hard", "domain": "Operations"},
    "Root Cause Analysis": {"aliases": ["root cause analysis"], "type": "hard", "domain": "Operations"},
    "Quality Improvement": {"aliases": ["quality improvement", "performance improvement", "six sigma"], "type": "hard", "domain": "Operations"},
    "Inspection": {"aliases": ["inspection"], "type": "hard", "domain": "Operations"},
    "Equipment Operation": {"aliases": ["equipment operation", "hand tools"], "type": "hard", "domain": "Operations"},
    "Forklift Operation": {"aliases": ["forklift operation"], "type": "hard", "domain": "Operations"},
    "Food Service": {"aliases": ["food service"], "type": "hard", "domain": "Operations"},
    "Production": {"aliases": ["production"], "type": "hard", "domain": "Operations"},
    "Transportation": {"aliases": ["transportation"], "type": "hard", "domain": "Operations"},
    "Emergency Response": {"aliases": ["emergency response"], "type": "hard", "domain": "Operations"},
    "Contract Administration": {"aliases": ["contract administration"], "type": "hard", "domain": "Operations"},
    "Project Coordination": {"aliases": ["project coordination", "coordination"], "type": "hard", "domain": "Management"},
    "Consulting": {"aliases": ["consulting"], "type": "hard", "domain": "Professional Skills"},
    "Curriculum Development": {"aliases": ["curriculum development"], "type": "hard", "domain": "Professional Skills"},
    # finance / accounting
    "Auditing": {"aliases": ["auditing", "audit"], "type": "hard", "domain": "Finance & Accounting"},
    "Billing": {"aliases": ["billing", "invoicing"], "type": "hard", "domain": "Finance & Accounting"},
    "Accounts Payable": {"aliases": ["accounts payable"], "type": "hard", "domain": "Finance & Accounting"},
    "Accounts Receivable": {"aliases": ["accounts receivable"], "type": "hard", "domain": "Finance & Accounting"},
    "Financial Statements": {"aliases": ["financial statements"], "type": "hard", "domain": "Finance & Accounting"},
    "GAAP": {"aliases": ["gaap"], "type": "hard", "domain": "Finance & Accounting"},
    "Variance Analysis": {"aliases": ["variance analysis"], "type": "hard", "domain": "Finance & Accounting"},
    "Banking": {"aliases": ["banking", "financial services"], "type": "hard", "domain": "Finance & Accounting"},
    "Insurance": {"aliases": ["insurance"], "type": "hard", "domain": "Finance & Accounting"},
    # tech
    "C++": {"aliases": ["c++"], "type": "hard", "domain": "Cloud & IT"},
    "C#": {"aliases": ["c#"], "type": "hard", "domain": "Cloud & IT"},
    "HTML": {"aliases": ["html"], "type": "hard", "domain": "Cloud & IT"},
    "CSS": {"aliases": ["css"], "type": "hard", "domain": "Cloud & IT"},
    "Jira": {"aliases": ["jira"], "type": "tool", "domain": "Cloud & IT"},
    "Jenkins": {"aliases": ["jenkins"], "type": "tool", "domain": "Cloud & IT"},
    "DevOps": {"aliases": ["devops"], "type": "hard", "domain": "Cloud & IT"},
    "Cloud Computing": {"aliases": ["cloud computing"], "type": "hard", "domain": "Cloud & IT"},
    "Windows": {"aliases": ["windows"], "type": "tool", "domain": "Cloud & IT"},
    "SharePoint": {"aliases": ["sharepoint"], "type": "tool", "domain": "Cloud & IT"},
    "Oracle": {"aliases": ["oracle"], "type": "tool", "domain": "Cloud & IT"},
    "Active Directory": {"aliases": ["active directory"], "type": "tool", "domain": "Cloud & IT"},
    "ERP Systems": {"aliases": ["erp systems"], "type": "tool", "domain": "Cloud & IT"},
    "Technical Support": {"aliases": ["technical support"], "type": "hard", "domain": "Cloud & IT"},
    "Information Technology": {"aliases": ["information technology"], "type": "hard", "domain": "Cloud & IT"},
    "Databases": {"aliases": ["databases"], "type": "hard", "domain": "Data & Analytics"},
    "Data Modeling": {"aliases": ["data modeling"], "type": "hard", "domain": "Data & Analytics"},
    "Business Intelligence": {"aliases": ["business intelligence"], "type": "hard", "domain": "Data & Analytics"},
    "Data Science": {"aliases": ["data science", "data interpretation"], "type": "hard", "domain": "Data & Analytics"},
    "Artificial Intelligence": {"aliases": ["artificial intelligence"], "type": "hard", "domain": "Data & Analytics"},
    "MATLAB": {"aliases": ["matlab"], "type": "tool", "domain": "Data & Analytics"},
    "SaaS": {"aliases": ["saas"], "type": "hard", "domain": "Cloud & IT"},
    "Microservices": {"aliases": ["microservices"], "type": "hard", "domain": "Cloud & IT"},
    "Robotics": {"aliases": ["robotics"], "type": "hard", "domain": "Cloud & IT"},
    "Computer Proficiency": {"aliases": ["computer proficiency", "pc skills", "computer literacy", "computer skills"], "type": "tool", "domain": "Professional Skills"},
    # Broad NER tokens — keep as own labels, marked generic later (do NOT map into Computer Proficiency)
    "Software": {"aliases": ["software"], "type": "tool", "domain": "Cloud & IT"},
    "Technical Skills": {"aliases": ["technical skills"], "type": "hard", "domain": "Professional Skills"},
    "CAD": {"aliases": ["cad"], "type": "tool", "domain": "Engineering & Construction"},
    "SolidWorks": {"aliases": ["solidworks"], "type": "tool", "domain": "Engineering & Construction"},
    "Blueprints": {"aliases": ["blueprints", "schematics"], "type": "hard", "domain": "Engineering & Construction"},
    "Electrical Systems": {"aliases": ["electrical", "electrical systems"], "type": "hard", "domain": "Engineering & Construction"},
    "Plumbing": {"aliases": ["plumbing"], "type": "hard", "domain": "Engineering & Construction"},
    "Carpentry": {"aliases": ["carpentry"], "type": "hard", "domain": "Engineering & Construction"},
    "Welding": {"aliases": ["welding"], "type": "hard", "domain": "Engineering & Construction"},
    "Painting": {"aliases": ["painting"], "type": "hard", "domain": "Engineering & Construction"},
    "Repair": {"aliases": ["repair", "installation"], "type": "hard", "domain": "Engineering & Construction"},
    "Estimating": {"aliases": ["estimating"], "type": "hard", "domain": "Engineering & Construction"},
    "Prototyping": {"aliases": ["prototyping"], "type": "hard", "domain": "Engineering & Construction"},
    "Product Development": {"aliases": ["product development"], "type": "hard", "domain": "Management"},
    "Instrumentation": {"aliases": ["instrumentation"], "type": "hard", "domain": "Engineering & Construction"},
    "Commissioning": {"aliases": ["commissioning"], "type": "hard", "domain": "Engineering & Construction"},
    "Sustainability": {"aliases": ["sustainability"], "type": "hard", "domain": "Operations"},
    # healthcare / behavioral
    "Infection Control": {"aliases": ["infection control"], "type": "hard", "domain": "Healthcare & Nursing"},
    "Cultural Competence": {"aliases": ["cultural competence"], "type": "soft", "domain": "Healthcare & Nursing"},
    "Stocking": {"aliases": ["stocking"], "type": "hard", "domain": "Operations"},
    "Cashiering": {"aliases": ["cashier", "cashiering"], "type": "hard", "domain": "Sales & Customer Success"},
    "First Aid": {"aliases": ["first aid"], "type": "hard", "domain": "Healthcare & Nursing"},
    "Social Work": {"aliases": ["social work"], "type": "hard", "domain": "Healthcare & Nursing"},
    "Psychology": {"aliases": ["psychology", "psychotherapy"], "type": "hard", "domain": "Healthcare & Nursing"},
    "Mental Health": {"aliases": ["mental health", "behavioral health", "crisis intervention"], "type": "hard", "domain": "Healthcare & Nursing"},
    "Pediatrics": {"aliases": ["pediatrics"], "type": "hard", "domain": "Healthcare & Nursing"},
    "Oncology": {"aliases": ["oncology"], "type": "hard", "domain": "Healthcare & Nursing"},
    "Critical Care": {"aliases": ["critical care"], "type": "hard", "domain": "Healthcare & Nursing"},
    "Radiology": {"aliases": ["radiology"], "type": "hard", "domain": "Healthcare & Nursing"},
    "Dentistry": {"aliases": ["dentistry", "dental"], "type": "hard", "domain": "Healthcare & Nursing"},
    "Internal Medicine": {"aliases": ["internal medicine", "primary care"], "type": "hard", "domain": "Healthcare & Nursing"},
    "Surgery": {"aliases": ["surgery"], "type": "hard", "domain": "Healthcare & Nursing"},
    "Wound Care": {"aliases": ["wound care"], "type": "hard", "domain": "Healthcare & Nursing"},
    "Care Coordination": {"aliases": ["care coordination"], "type": "hard", "domain": "Healthcare & Nursing"},
    "Evidence-Based Practice": {"aliases": ["evidencebased practice", "evidence-based practice"], "type": "hard", "domain": "Healthcare & Nursing"},
    "Clinical Skills": {"aliases": ["clinical skills", "clinical experience"], "type": "hard", "domain": "Healthcare & Nursing"},
    "Diagnosis": {"aliases": ["diagnosis", "treatment"], "type": "hard", "domain": "Healthcare & Nursing"},
    "Physical Therapy": {"aliases": ["physical therapy", "rehabilitation"], "type": "hard", "domain": "Healthcare & Nursing"},
    "Phlebotomy": {"aliases": ["phlebotomy"], "type": "hard", "domain": "Healthcare & Nursing"},
    "Child Development": {"aliases": ["child development"], "type": "hard", "domain": "Healthcare & Nursing"},
    "Marriage and Family Therapy": {"aliases": ["marriage and family therapy"], "type": "hard", "domain": "Healthcare & Nursing"},
    "Advocacy": {"aliases": ["advocacy"], "type": "soft", "domain": "Healthcare & Nursing"},
    "Problem Resolution": {"aliases": ["problem resolution"], "type": "soft", "domain": "Professional Skills"},
    "Filing": {"aliases": ["filing"], "type": "hard", "domain": "Professional Skills"},
    "Implementation": {"aliases": ["implementation"], "type": "hard", "domain": "Professional Skills"},
    "Monitoring": {"aliases": ["monitoring"], "type": "hard", "domain": "Professional Skills"},
    # Keep exact NER tokens for sense-disambiguation upstream; no ultra-short aliases for summary
    "Analysis": {"aliases": ["analysis", "data analysis"], "type": "hard", "domain": "Data & Analytics"},
    "Development": {"aliases": ["development", "software development"], "type": "hard", "domain": "Professional Skills"},
    "Quality": {"aliases": ["quality", "quality assurance"], "type": "hard", "domain": "Operations"},
    "Procedures": {"aliases": ["standard operating procedures", "operating procedures"], "type": "hard", "domain": "Operations"},
    "Equity": {"aliases": ["equity"], "type": "soft", "domain": "Professional Skills"},
}

SKILL_META.update(SKILL_META_ROUND2)

# Ambiguous skills: aliases only for summary matching; NER matching can use aliases + safe forms
SKILL_DICT = {
    name: sorted(set(a.lower() for a in meta["aliases"]))
    for name, meta in SKILL_META.items()
}
SKILL_TYPE = {name: meta["type"] for name, meta in SKILL_META.items()}
COURSE_DOMAIN = {name: meta["domain"] for name, meta in SKILL_META.items()}

# ---------------------------------------------------------------------------
# Certifications
# ---------------------------------------------------------------------------
CERT_DICT = {
    "RN": ["registered nurse", "rn license", "rn licensed", "licensed registered nurse", "rn"],
    "LPN": ["licensed practical nurse", "lpn license", "licensed vocational nurse", "lvn"],
    "CNA": ["certified nursing assistant", "cna certification"],
    "NP": ["nurse practitioner", "aprn"],
    "PA": ["physician assistant", "pa-c", "pa c"],
    "BLS": ["basic life support", "bls certification", "bls certified"],
    "ACLS": ["advanced cardiac life support", "acls certification", "acls certified"],
    "PALS": ["pediatric advanced life support", "pals certification", "pals"],
    "CPR": ["cpr certified", "cpr certification"],
    "CDL": [
        "commercial driver's license", "commercial drivers license", "cdl license", "cdl",
        "class a commercial", "class b commercial", "commercial license",
        "class a or class b commercial",
    ],
    "Driver's License": [
        "driver's license", "drivers license", "driver licence", "drivers licence",
        "valid driver's license", "valid drivers license", "state driver's license",
        "driving license", "driving licence", "uk driving license", "uk driving licence",
        "full driving license", "full driving licence", "clean driving licence",
        "clean driving license", "florida driver's license",
        "class c license", "class b license", "class c or b license",
        "class c or b",
    ],
    "Medical License": [
        "state medical license", "medical license", "medical licence",
        "physician license", "licensed physician", "unrestricted medical license",
        "active medical license", "current medical license", "medical licensure",
    ],
    "Board Certification": [
        "board certified", "board-certified", "board eligible", "board-eligible",
        "board certification",
    ],
    "Bar Admission": [
        "bar admission", "admitted to the bar", "state bar", "licensed to practice law",
        "bar license", "bar licence", "qualified solicitor", "solicitor qualification",
    ],
    "PE License": [
        "professional engineer", "pe license", "p.eng", "p.eng.", "licensed professional engineer",
    ],
    "309A Electrician Licence": [
        "309a", "309a electrician", "309a licence", "309a license", "journeyperson electrician licence",
    ],
    "CHRP/CHRL": ["chrp", "chrl", "chrp/chrl", "certified human resources professional"],
    "Emergency Medical Responder": [
        "emergency medical responder", "emr certification", "emr certified",
    ],
    "ARRT": ["arrt", "arrt (ct)", "arrt ct", "american registry of radiologic"],
    "GPhC Registration": ["gphc", "gphc registration", "general pharmaceutical council"],
    "ACCA": ["acca", "aca/acca", "association of chartered certified accountants"],
    "AAT": ["aat", "association of accounting technicians"],
    "ServiceNow CIS": ["servicenow cis", "cis servicenow", "servicenow certified"],
    "PMP": ["project management professional", "pmp certification", "pmp certified"],
    "CPA": ["certified public accountant", "cpa license"],
    "CFA": ["chartered financial analyst", "cfa charter"],
    "AWS Certified": ["aws certified", "aws certification"],
    "Azure Certified": ["azure certified", "az-900", "az-104"],
    "CompTIA Security+": ["security+", "comptia security", "security plus"],
    "CompTIA A+": ["comptia a+", "a+ certification"],
    "Cisco CCNA": ["ccna", "cisco certified network associate"],
    "SHRM": ["shrm-cp", "shrm-scp"],
    "PHR": ["phr certification", "professional in human resources"],
    "Cosmetology License": ["cosmetology license", "licensed cosmetologist"],
    "Barber License": ["barber license", "licensed barber"],
    # Gaps found on the holdout sample
    "CIPD": ["cipd", "cipd level", "chartered institute of personnel"],
    "LMFT": ["lmft", "licensed marriage and family therapist"],
    "LPC": ["lpc", "licensed professional counselor"],
    "LCSW": ["lcsw", "licensed clinical social worker"],
    "RDCS": ["rdcs", "registered diagnostic cardiac sonographer"],
    "RCS": ["rcs", "registered cardiac sonographer"],
    "Veterinary License": [
        "veterinary license", "veterinary licence", "dvm license", "dvm licence",
        "licensed veterinarian", "licensed veterinary",
    ],
    "Teaching License": [
        "teaching license", "teaching licence", "teacher license", "teacher licence",
        "state teaching license", "professional educator license", "pel license",
        "educator license",
    ],
}

CERT_META_DOMAIN = {k: "Healthcare & Nursing" if k in {"RN","LPN","CNA","NP","BLS","ACLS","PALS","CPR"} else "Other" for k in CERT_DICT}

# ---------------------------------------------------------------------------
# Education patterns (incl. healthcare professional degrees)
# ---------------------------------------------------------------------------
# NOTE: never use m.?d.? / d.?o.? — bare "do"/"md" false-positives (stage-1 bug).
# MD / DO must include periods (M.D. / D.O.) to avoid "do" / state codes.
EDU_PATTERNS = [
    (
        "professional_doctorate",
        # Note: trailing \b after "M.D." fails because "." is non-word; use (?!\w)
        r"(?i)(?:"
        r"\bM\.D\.(?!\w)|\bD\.O\.(?!\w)|\bD\.V\.M\.(?!\w)|\bDVM\b|"
        r"\bPharm\.?\s*D\b|\bPharmD\b|\bJ\.D\.(?!\w)|"
        # bare JD only with legal cue or J.D. — exclude JD.com / Sports / Group / attached JD
        r"(?<![A-Za-z])JD(?![A-Za-z])(?!\s*(?:Edwards|Finish|com\b|Sports|Group))|"
        r"\bjuris\s+doctor(?:ate)?\b|"
        r"\bDNP\b|\bDDS\b|\bDMD\b|"
        r"\bdoctor of (?:medicine|osteopathic medicine|pharmacy|veterinary(?:\s+medicine)?|nursing practice|jurisprudence)\b"
        r")",
    ),
    ("phd", r"(?i)\bPh\.?\s?D\.?\b|\bPhD\b|\bdoctoral(?:\s+degree)?\b(?!\s+of\s+jurisprudence)"),
    # Never bare "MS" in MS Office; never bare "master" in master data.
    # Allow: master's/master degree, Master's (as degree word), MBA, M.S., MS in/or PhD, MSN.
    ("master",
     r"(?i)(?:"
     r"\bmaster'?s?\s+degree\b|"
     r"\bMBA\b|"
     r"\bMSN\b|"
     r"\bM\.S\.(?!\w)|"
     r"\bM\.A\.(?!\w)|"
     r"\bMS\s+in\b|"
     r"\bMS\s*(?:/|or)\s*Ph\.?D\.?\b|"
     r"\bMS\b(?=\s*(?:in\b|or\b|/|,))"
     r"(?!\s*(?:Office|Word|Excel|Project|Teams|PowerPoint|Outlook)\b)|"
     r"\bmaster of (?:science|arts|business|science in nursing)\b|"
     r"\bmaster'?s\b(?!\s+(?:data|contract|schedule|sanitation|brand|bedroom|key|builder))"
     r")"),
    ("bachelor",
     r"(?i)\bbachelor'?s?(?:\s+degree)?\b|\bB\.S\.(?!\w)|\bB\.A\.(?!\w)|\bBS\b|\bBA\b|\bBSN\b|"
     r"\bbachelor of (?:science|arts|science in nursing)\b|\b4[- ]year degree\b|\bundergraduate degree\b"),
    # NEVER bare "as"/"associate"/"AA"/"AS" — only explicit degree contexts.
    # "Sales Associate", "Associate Discount", "as well as" must not match.
    ("associate",
     r"(?i)(?:"
     r"\bassociate'?s?\s+degree\b|"
     r"\bassociates\s+degree\b|"
     r"\b2[- ]year degree\b|"
     r"\bA\.A\.(?!\w)(?:\s*(?:degree|diploma))?|"
     r"\bA\.S\.(?!\w)(?:\s*(?:degree|diploma))?|"
     r"\bAAS\b(?:\s*(?:degree|diploma))?|"
     r"\bASN\b|\bADN\b|"
     r"\bAA\s+degree\b|"
     r"\bAS\s+degree\b|"
     r"\bassociate(?:'?s)?\s+(?:degree\s+)?in\s+nursing\b|"
     # "Associate or Baccalaureate School of Nursing"
     r"\bassociate\s+or\s+baccalaureate\b"
     r")"),
    ("high_school", r"(?i)\bhigh school(?:\s+diploma|\s+or\s+equivalent)?\b|\bGED\b"),
]

# Bare "degree in X" / "a degree in" with no level → bachelor (edu recall)
_DEGREE_IN_RE = re.compile(r"(?i)\b(?:a|an|the)?\s*degree\s+in\b|\bcollege\s+degree\b")


def normalize_jd_text(text: str) -> str:
    """Normalize curly quotes/dashes so license/degree regexes match real JDs."""
    if not isinstance(text, str) or not text:
        return text
    return (
        text.replace("\u2019", "'")
        .replace("\u2018", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\u00a0", " ")
    )

EDU_RANK = {
    "high_school": 1,
    "associate": 2,
    "bachelor": 3,
    "master": 4,
    "phd": 5,
    "professional_doctorate": 6,
}

# English word numbers for "Five (5) years" / "two years"
_YOE_WORD2NUM = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20,
}
_YOE_WORD_ALT = "|".join(_YOE_WORD2NUM.keys())

# Ending cues: experience / exp / PQE / "in relevant position"
_YOE_END_CUE = (
    r"(?:\bexperience\b|\bexp\b|\bPQE\b|\bPQE\+|"
    r"\bin\s+(?:a\s+)?relevant\s+position\b|"
    r"\bin\s+(?:a\s+)?related\s+(?:role|position|field)\b)"
)

# years of experience — digits; also yrs / 1-year / PQE
YOE_RE = re.compile(
    r"(?:(?P<atleast>at\s+least|minimum(?:\s+of)?)\s+)?"
    r"(?<!\d)(?P<min>\d{1,2})"
    r"(?:"
    r"\s*(?:-|–|to)\s*(?P<max>\d{1,2})\s*\+?"
    r"|\s*\+"
    r")?"
    r"(?:-|\s+)(?:years?|yrs?)(?:\s+plus)?"
    r"(?!\s*(?:of\s+age|old\b|or\s+older|of\s+age\b))"
    r"(?P<tail>(?:(?!\b(?:of\s+age|or\s+older)\b)[^.;\n]){0,80}?)"
    + _YOE_END_CUE,
    re.I,
)

# "Five (5) to ten (10) years of experience" / "Two years of supervisor experience"
YOE_WORD_RE = re.compile(
    r"(?:(?P<atleast>at\s+least|minimum(?:\s+of)?)\s+)?"
    r"(?P<wmin>" + _YOE_WORD_ALT + r"|\d{1,2})"
    r"(?:\s*\(\s*(?P<pmin>\d{1,2})\s*\))?"
    r"(?:"
    r"\s*(?:-|–|to)\s*"
    r"(?P<wmax>" + _YOE_WORD_ALT + r"|\d{1,2})"
    r"(?:\s*\(\s*(?P<pmax>\d{1,2})\s*\))?"
    r"|\s*\+"
    r")?"
    r"(?:-|\s+)(?:years?|yrs?)(?:\s+plus)?"
    r"(?!\s*(?:of\s+age|old\b|or\s+older))"
    r"(?P<tail>(?:(?!\b(?:of\s+age|or\s+older)\b)[^.;\n]){0,80}?)"
    + _YOE_END_CUE,
    re.I,
)
# "1 year (preferred)" / "5 years (required)" without the word experience
YOE_PAREN_STATUS_RE = re.compile(
    r"(?<!\d)(?P<min>\d{1,2})"
    r"(?:\s*(?:-|–|to)\s*(?P<max>\d{1,2}))?"
    r"(?:-|\s+)(?:years?|yrs?)\s*\(\s*(?P<pstatus>preferred|required)\s*\)",
    re.I,
)
# Extra reject: "18 years or older ... experience" even if backtracking sneaks through
_YOE_AGE_REJECT_RE = re.compile(
    r"(?i)\b\d{1,2}\s*years?\s+(?:of\s+age|old|or\s+older)\b"
)

# Company heritage / brand history — NOT a candidate YOE requirement
# e.g. "Backed by over 120 years of experience", "more than 100 years of experience"
_YOE_COMPANY_HISTORY_RE = re.compile(
    r"(?i)(?:"
    r"\bbacked\s+by\b|"
    r"\bproud\s+of\b|"
    r"\bfamily[- ]owned\b|"
    r"\b(?:established|founded|serving)\b|"
    r"\bsince\s+\d{4}\b|"
    r"\bour\s+(?:company|organization|organisation|firm|history)\b|"
    r"\b(?:over|more\s+than|nearly|almost)\s+\d+\s+years?\s+of\s+experience\b|"
    r"\bwith\s+over\b|"
    r"\bfor\s+over\b|"
    r"\bcombined\s+experience\b|"
    r"\bin\s+the\s+(?:\w+\s+){0,3}industry\b|"
    r"\bpast\s+\d+\s+years\b|"
    r"\bwe\s+(?:have|bring|offer)\b"
    r")"
)
_YOE_REQUIREMENT_CUE_RE = re.compile(
    r"(?i)\b(?:require[ds]?|must|minimum|at\s+least|necessary|needed|seeking|looking\s+for)\b"
)

# Only named tools/tech count as skill_specific; domain years ("restoration",
# "multi-store sales management") stay overall so they fill yoe_min_overall.
_YOE_SKILL_TAIL_RE = re.compile(
    r"(?i)\b(?:in|with|of)\s+(?:python|java|javascript|typescript|sql|salesforce|"
    r"excel|aws|azure|react|oracle|sap|hadoop|kubernetes|docker|tableau|"
    r"power\s*bi|c\+\+|c#)\b|"
    r"\b(?:python|java|sql|salesforce|excel|aws|azure)\b"
)
_YOE_PREFERRED_CUE = re.compile(
    r"(?i)\bprefer(?:red|ence)?\b|\ba plus\b|nice to have|desired|ideally\b"
)
_YOE_EDU_EQUIV_REJECT = re.compile(
    r"(?i)\byears?\s+of\s+education\b|\byear\s+degree\b|\bdegree\s*=\s*\d|\bexperience\s*=\s*\d\s*year"
)

NO_DEGREE_RE = re.compile(
    r"(?i)\bno\s+(?:\w+\s+){0,4}degree\s+(?:is\s+)?(?:required|needed)\b|"
    r"\bdegree\s+(?:is\s+)?not\s+required\b|"
    r"\bwithout\s+(?:a\s+)?degree\b|"
    r"\bno\s+education(?:al)?\s+requirement"
)

EDU_REQUIRED_CUE = re.compile(
    r"(?i)\b(?:must|requires?|required|requirements?|minimum|mandatory|necessary)\b"
)
EDU_PREFERRED_CUE = re.compile(
    r"(?i)\bprefer(?:red|ence)?\b|\ba plus\b|nice to have|desired|ideally\b"
)

CERT_REQUIRE_CUE = re.compile(
    r"(?i)\b(?:licen[cs]e[ds]?|certified|certification|credential|must\s+have|required)\b"
)


def requirement_text(summary: str):
    """Return (text_for_qualifications, has_req_section).

    Prefer requirements/preferred sections. If none found, fall back to the full
    JD with benefits / company / eeo stripped (stage 5) — never raw full text.
    """
    if not isinstance(summary, str) or not summary.strip():
        return "", False
    # lazy import — skill_refinement owns section typing
    from skill_refinement import split_sections_typed

    sections = split_sections_typed(summary)
    if not sections:
        return summary.strip(), False

    req_parts = [
        s["text"] for s in sections
        if s["section_type"] in {"requirements", "preferred"}
    ]
    if any(p.strip() for p in req_parts):
        return "\n".join(p for p in req_parts if p.strip()).strip(), True

    # fallback: exclude benefits / company / eeo (never raw full text)
    from skill_refinement import strip_boilerplate

    allowed = [
        s["text"] for s in sections
        if s["section_type"] not in {"benefits", "company", "eeo"}
    ]
    joined = "\n".join(p for p in allowed if p.strip()).strip()
    if not joined:
        joined = summary.strip()
    joined = strip_boilerplate(joined)
    # belt-and-suspenders: drop residual benefits/about blocks
    joined = re.sub(
        r"(?is)\b(?:benefits|perks|what we offer|compensation(?:\s+and\s+benefits)?)\s*:.*?"
        r"(?=\n[A-Z][^\n]{0,40}:|\n\n|\Z)",
        " ",
        joined,
    )
    joined = re.sub(
        r"(?is)\b(?:about (?:us|the company)|who we are|our company|equal opportunity|eeo)\s*:.*?"
        r"(?=\n[A-Z][^\n]{0,40}:|\n\n|\Z)",
        " ",
        joined,
    )
    return re.sub(r"\s+", " ", joined).strip(), False


def _is_company_history_yoe(text: str, start: int, end: int) -> bool:
    """True for brand/heritage phrases, not candidate requirements.

    'Backed by over 120 years of experience' = company age, not YOE.
    Left digit boundary already blocks truncating 120→20; this catches 2-digit
    heritage lines like 'over 25 years of experience' in about-us copy.

    Scope = the current sentence only (do not bleed into a later Requirements line).
    """
    # sentence bounds
    left = max(text.rfind(".", 0, start), text.rfind("\n", 0, start), text.rfind("!", 0, start), text.rfind("?", 0, start))
    right_candidates = [text.find(ch, end) for ch in ".\n!?"]
    right_candidates = [i for i in right_candidates if i != -1]
    right = min(right_candidates) if right_candidates else len(text)
    sentence = text[left + 1:right]
    if not _YOE_COMPANY_HISTORY_RE.search(sentence):
        return False
    if _YOE_REQUIREMENT_CUE_RE.search(sentence):
        return False
    return True


def extract_yoe_records(text: str, *, section_type: str | None = None) -> list[dict]:
    """Per-mention YOE rows.

    - benefits / company / eeo sections are skipped entirely
    - company-history phrasing dropped even in intro/other blobs
    - ``(?<!\\d)`` prevents reading 20 out of 120
    """
    if not isinstance(text, str) or not text.strip():
        return []
    if section_type in {"benefits", "company", "eeo"}:
        return []
    text = normalize_jd_text(text)
    rows = []
    covered: list[tuple[int, int]] = []

    def _overlaps(a: int, b: int) -> bool:
        return any(not (b <= x or a >= y) for x, y in covered)

    def _append_yoe(lo, hi, is_plus, yoe_type, yoe_status, raw, start, end):
        if _overlaps(start, end):
            return
        evidence = re.sub(r"\s+", " ", text[max(0, start - 30):end + 20]).strip()
        rows.append({
            "yoe_min": lo,
            "yoe_max": hi,
            "yoe_plus": is_plus,
            "yoe_type": yoe_type,
            "yoe_status": yoe_status,
            "section_type": section_type,
            "matched_text": raw.strip(),
            "evidence": evidence[:250],
            "char_start": start,
            "char_end": end,
        })
        covered.append((start, end))

    def _parse_yoe_token(tok: str | None, paren: str | None = None) -> int | None:
        if paren:
            return int(paren)
        if tok is None:
            return None
        t = tok.lower().strip()
        if t in _YOE_WORD2NUM:
            return _YOE_WORD2NUM[t]
        if re.fullmatch(r"\d{1,2}", t):
            return int(t)
        return None

    def _emit_from_match(m, *, min_key="min", max_key="max", word_mode=False):
        if _is_company_history_yoe(text, m.start(), m.end()):
            return
        span = text[m.start():m.end()]
        if _YOE_AGE_REJECT_RE.search(span) or re.search(r"(?i)\byears?\s+or\s+older\b", span):
            return
        if _YOE_EDU_EQUIV_REJECT.search(span) or _YOE_EDU_EQUIV_REJECT.search(
            text[max(0, m.start() - 20):m.end() + 40]
        ):
            return
        raw = m.group(0)
        gd = m.groupdict()
        if word_mode:
            lo = _parse_yoe_token(gd.get("wmin"), gd.get("pmin"))
            hi = _parse_yoe_token(gd.get("wmax"), gd.get("pmax")) if gd.get("wmax") else None
        else:
            lo = int(gd["min"])
            hi = int(gd["max"]) if gd.get("max") else None
        if lo is None or lo > 40:
            return
        atleast = bool(gd.get("atleast"))
        is_plus = bool(
            atleast
            or re.search(r"(?:years?|yrs?)\s+plus", raw, re.I)
            or re.search(r"\d\s*\+\s*(?:years?|yrs?)", raw, re.I)
            or re.search(r"(?:" + _YOE_WORD_ALT + r")\s*\(\s*\d+\s*\)\s*\+", raw, re.I)
            or bool(re.search(r"\+\s*(?:years?|yrs?)", raw, re.I))
            or ("+" in raw and hi is None and not gd.get("wmax") and not gd.get("max"))
        )
        if hi is not None:
            if hi < lo or hi > 40:
                return
        elif is_plus:
            hi = None
        else:
            hi = lo
        tail = gd.get("tail") or ""
        yoe_type = "skill_specific" if _YOE_SKILL_TAIL_RE.search(tail) else "overall"
        left = max(text.rfind(".", 0, m.start()), text.rfind("\n", 0, m.start()), 0)
        right_cands = [text.find(ch, m.end()) for ch in ".\n"]
        right_cands = [i for i in right_cands if i != -1]
        right = min(right_cands) if right_cands else len(text)
        sent = text[left:right]
        if section_type == "preferred" or _YOE_PREFERRED_CUE.search(sent):
            yoe_status = "preferred"
        else:
            yoe_status = "required"
        _append_yoe(lo, hi, is_plus, yoe_type, yoe_status, raw, m.start(), m.end())

    # Word-number forms first (Five (5) years / two years / 5+ years in relevant position)
    for m in YOE_WORD_RE.finditer(text):
        _emit_from_match(m, word_mode=True)

    for m in YOE_RE.finditer(text):
        _emit_from_match(m, word_mode=False)

    for m in YOE_PAREN_STATUS_RE.finditer(text):
        if _is_company_history_yoe(text, m.start(), m.end()):
            continue
        lo = int(m.group("min"))
        if lo > 40:
            continue
        max_g = m.group("max")
        hi = int(max_g) if max_g else lo
        if hi < lo or hi > 40:
            continue
        status = "preferred" if m.group("pstatus").lower() == "preferred" else "required"
        if section_type == "preferred":
            status = "preferred"
        _append_yoe(lo, hi, False, "overall", status, m.group(0), m.start(), m.end())
    return rows


def _min_yoe(recs: list[dict]):
    if not recs:
        return None, None, False
    if len(recs) == 1:
        return recs[0]["yoe_min"], recs[0]["yoe_max"], False
    keys = {(r["yoe_min"], r["yoe_max"]) for r in recs}
    if len(keys) == 1:
        lo, hi = next(iter(keys))
        return lo, hi, False
    return min(r["yoe_min"] for r in recs), None, True


def aggregate_yoe(records: list[dict]) -> dict:
    """Job-level YOE.

    Round5: if there is NO overall mention, leave yoe_*_overall empty —
    skill-specific years stay only in the detail table. Expose yoe_min_any_skill.

    Round6: split required vs preferred. ``yoe_min_overall`` = required, falling
    back to preferred when required is missing (matches Claude gold which counts
    preferred years).
    """
    empty = {
        "yoe_min_overall": None, "yoe_max_overall": None, "yoe_multi": False,
        "yoe_min_any_skill": None,
        "yoe_min_required": None, "yoe_max_required": None,
        "yoe_min_preferred": None, "yoe_max_preferred": None,
    }
    if not records:
        return empty
    skill_recs = [r for r in records if r.get("yoe_type") == "skill_specific"]
    overall = [r for r in records if r.get("yoe_type") == "overall"]
    any_skill_min = min((r["yoe_min"] for r in skill_recs), default=None)

    req = [r for r in overall if r.get("yoe_status") != "preferred"]
    pref = [r for r in overall if r.get("yoe_status") == "preferred"]
    rmin, rmax, rmulti = _min_yoe(req)
    pmin, pmax, pmulti = _min_yoe(pref)

    if rmin is not None:
        omin, omax, omulti = rmin, rmax, rmulti
    else:
        omin, omax, omulti = pmin, pmax, pmulti

    return {
        "yoe_min_overall": omin,
        "yoe_max_overall": omax,
        "yoe_multi": omulti,
        "yoe_min_any_skill": any_skill_min,
        "yoe_min_required": rmin,
        "yoe_max_required": rmax,
        "yoe_min_preferred": pmin,
        "yoe_max_preferred": pmax,
    }


def extract_yoe(text: str):
    """Backward-compatible (yoe_min, yoe_max)."""
    agg = aggregate_yoe(extract_yoe_records(text))
    return agg["yoe_min_overall"], agg["yoe_max_overall"]


def _local_edu_status(sent: str, match_start: int, match_end: int, section_type: str | None) -> str:
    """Judge required/preferred/conflict from cues NEAR this degree only (round5)."""
    # Don't split on periods inside M.D. / Ph.D. — use comma/semicolon clause bounds
    left_bound = max(
        sent.rfind(",", 0, match_start),
        sent.rfind(";", 0, match_start),
        match_start - 48,
        0,
    )
    right_candidates = [sent.find(ch, match_end) for ch in ",;"]
    right_candidates = [i for i in right_candidates if i != -1]
    right_bound = min(right_candidates) if right_candidates else min(len(sent), match_end + 48)
    local = sent[left_bound:right_bound]
    has_req = bool(EDU_REQUIRED_CUE.search(local))
    has_pref = bool(EDU_PREFERRED_CUE.search(local))

    # Preferred section + explicit required on this degree → conflict (do not overwrite)
    if section_type == "preferred" and has_req:
        return "conflict"
    if has_req and has_pref:
        return "conflict"
    if has_req:
        return "required"
    if has_pref:
        return "preferred"
    if section_type == "preferred":
        return "preferred"
    if section_type == "requirements":
        return "required"
    if EDU_REQUIRED_CUE.search(sent):
        return "required"
    if EDU_PREFERRED_CUE.search(sent):
        return "preferred"
    # Nursing ADN/ASN without a nearby cue is still a hard credential on clinical JDs
    if re.search(r"(?i)\b(?:ADN|ASN|associate(?:'?s)?\s+degree\s+in\s+nursing)\b", sent):
        return "required"
    return "mentioned"


def extract_education_records(text: str, *, has_req_section: bool = False,
                              section_type: str | None = None) -> list[dict]:
    """Per-degree education with local required/preferred cues (round5)."""
    if not isinstance(text, str) or not text.strip():
        return []
    if section_type in {"benefits", "company", "eeo"}:
        return []
    text = normalize_jd_text(text)
    rows = []
    if NO_DEGREE_RE.search(text):
        m = NO_DEGREE_RE.search(text)
        rows.append({
            "edu_level": None,
            "edu_status": "not_required",
            "edu_relation": None,
            "section_type": section_type,
            "matched_text": m.group(0) if m else "no degree required",
            "evidence": re.sub(r"\s+", " ", text[max(0, m.start() - 20):m.end() + 20]).strip()[:250] if m else "",
            "char_start": m.start() if m else None,
            "char_end": m.end() if m else None,
            "sentence_id": None,
        })

    # Split on newline / bullet / "; " — avoid cutting inside M.D. / Ph.D.
    # Soft-split on ". " only when the period is not part of an abbreviation (M.D./Ph.D./B.S.).
    clauses: list[tuple[int, str]] = []
    for sid, block in enumerate(re.split(r"(?:\n+|•|\s*;\s*)", text)):
        block = block.strip()
        if not block:
            continue
        parts = re.split(r"(?<![A-Z])\.(?!\w)\s+(?=[A-Z])", block)
        # Fallback: if soft-split emptied or kept one blob, keep whole block
        if not parts:
            parts = [block]
        for part in parts:
            part = part.strip()
            if part:
                clauses.append((sid, part))

    for sid, sent in clauses:
        found = []
        for level, pat in EDU_PATTERNS:
            for m in re.finditer(pat, sent):
                # bare JD without legal context
                if level == "professional_doctorate" and re.fullmatch(r"JD", m.group(0), re.I):
                    ctx = sent[max(0, m.start() - 30):m.end() + 30]
                    if re.search(r"(?i)attached\s+JD|JD\s*(?:com|Sports|Group|Edwards|Finish)", ctx):
                        continue
                    if not re.search(r"(?i)juris|law|legal|attorney|counsel", ctx) and "J.D" not in m.group(0):
                        if not re.search(r"(?i)degree|doctor", sent):
                            continue
                # MS Office / master data / scrum master are not degrees
                if level == "master":
                    ctx = sent[max(0, m.start() - 5):m.end() + 25]
                    if re.search(
                        r"(?i)\bMS\s*(?:Office|Word|Excel|Project|Teams|PowerPoint|Outlook)\b|"
                        r"\bmaster\s+(?:data|contract|schedule|sanitation|brand|bedroom|key)\b|"
                        r"\bscrum\s+master\b",
                        ctx,
                    ):
                        continue
                    # bare "master" (no 's) only OK as "master degree" / "master of"
                    if re.fullmatch(r"(?i)master", m.group(0)):
                        continue
                found.append((m.start(), m.end(), level, m.group(0)))
        # "degree in Finance" / "college degree" with no level word → bachelor
        if not found:
            mdeg = _DEGREE_IN_RE.search(sent)
            if mdeg and not re.search(r"(?i)\bgraduate\s+of\b", sent):
                found.append((mdeg.start(), mdeg.end(), "bachelor", mdeg.group(0)))
        if not found:
            continue
        found.sort(key=lambda x: x[0])
        relation = None
        if len(found) > 1:
            if re.search(r"(?i)\bor\b", sent):
                relation = "or"
            elif re.search(r"(?i)\band\b", sent):
                relation = "and"
            else:
                relation = "multiple"

        for a, b, level, matched in found:
            status = _local_edu_status(sent, a, b, section_type)
            rows.append({
                "edu_level": level,
                "edu_status": status,
                "edu_relation": relation if len(found) > 1 else None,
                "section_type": section_type,
                "matched_text": matched,
                "evidence": re.sub(r"\s+", " ", sent)[:250],
                "char_start": None,
                "char_end": None,
                "sentence_id": sid,
            })
    return rows


def summarize_education(records: list[dict]):
    """Job-level education (round5).

    Within one sentence + or → keep minimum as required, rest in alternatives.
    Across sentences → take the MAX (strictest) required level.
    """
    if not records:
        return {
            "edu_required": None,
            "edu_preferred": None,
            "edu_mentioned": None,
            "edu_alternatives": None,
            "edu_not_required": False,
            "edu_or_equiv": False,
            "edu_status": "unknown",
        }
    not_req = any(r["edu_status"] == "not_required" for r in records)
    has_conflict = any(r["edu_status"] == "conflict" for r in records)

    # group required (+ conflict treated as required for aggregation, flagged)
    req_rows = [r for r in records if r["edu_status"] in {"required", "conflict"} and r["edu_level"]]
    prefs = [r["edu_level"] for r in records if r["edu_status"] == "preferred" and r["edu_level"]]
    ments = [r["edu_level"] for r in records if r["edu_status"] == "mentioned" and r["edu_level"]]

    edu_required = None
    edu_alternatives: list[str] = []
    if req_rows:
        by_sent: dict = {}
        for r in req_rows:
            by_sent.setdefault(r.get("sentence_id"), []).append(r)
        sentence_mins = []
        for sid, rows in by_sent.items():
            levels = [x["edu_level"] for x in rows]
            if any(x.get("edu_relation") == "or" for x in rows) and len(set(levels)) > 1:
                ordered = sorted(set(levels), key=lambda x: EDU_RANK[x])
                sentence_mins.append(ordered[0])
                edu_alternatives.extend(ordered[1:])
            else:
                # same sentence without or → strictest in that sentence
                sentence_mins.append(max(levels, key=lambda x: EDU_RANK[x]))
        # across sentences: strictest
        edu_required = max(sentence_mins, key=lambda x: EDU_RANK[x])
        # Nursing ADN + "enrolled in BSN" ladder: gold takes associate as the
        # current required rung, bachelor as alternative.
        if edu_required == "bachelor":
            adn_hit = any(
                r.get("edu_level") == "associate"
                and re.search(
                    r"(?i)\bADN\b|associate(?:'?s)?\s+degree\s+in\s+nursing|"
                    r"associate\s+or\s+baccalaureate",
                    f"{r.get('matched_text', '')} {r.get('evidence', '')}",
                )
                for r in req_rows
            )
            if adn_hit:
                edu_required = "associate"
                if "bachelor" not in edu_alternatives:
                    edu_alternatives.append("bachelor")
        # alternatives: other required levels not equal to edu_required
        for r in req_rows:
            if r["edu_level"] != edu_required and r["edu_level"] not in edu_alternatives:
                edu_alternatives.append(r["edu_level"])

    edu_preferred = max(prefs, key=lambda x: EDU_RANK[x], default=None)
    edu_mentioned = min(ments, key=lambda x: EDU_RANK[x], default=None)
    if not_req and edu_required is None:
        status = "not_required"
    elif has_conflict:
        status = "conflict"
    elif edu_required:
        status = "required"
    elif edu_preferred:
        status = "preferred"
    elif edu_mentioned:
        status = "mentioned"
    else:
        status = "unknown"
    alts = [a for a in edu_alternatives if a != edu_required]
    return {
        "edu_required": None if not_req and not edu_required else edu_required,
        "edu_preferred": edu_preferred,
        "edu_mentioned": edu_mentioned,
        "edu_alternatives": "|".join(dict.fromkeys(alts)) if alts else None,
        "edu_not_required": not_req,
        "edu_or_equiv": False,
        "edu_status": status,
    }


def extract_education_levels(text: str):
    """Return (edu_required, edu_preferred, edu_or_equiv) — stage-5 semantics.

    Required only if in a requirements blob or sentence has must/required.
    Explicit "no degree required" → (None, preferred?, False) with no false required.
    """
    if not isinstance(text, str) or not text.strip():
        return None, None, False
    # Assume caller passes requirement_text; mark has_req_section=True when non-empty
    records = extract_education_records(text, has_req_section=True)
    summary = summarize_education(records)
    or_equiv = bool(re.search(r"(?i)or equivalent (?:work )?experience", text))
    return summary["edu_required"], summary["edu_preferred"], or_equiv


_CERT_SUPERVISION_LEFT_RE = re.compile(
    r"(?i)(?:under\s+(?:the\s+)?(?:direct\s+)?supervision\s+of|"
    r"supervised\s+by|reports?\s+to|reporting\s+to|oversight\s+of)\s*"
    r"(?:an?\s+|the\s+)?(?:\w+\s+){0,4}$"
)


def _cert_alias_ok(canonical: str, alias: str, text: str, start: int, end: int) -> bool:
    """Reject JD Edwards / JD.com / state PA abbreviations (round4).

    Round8: 'under the supervision of an RN or LPN' / 'reports to RN' are not
    certificates required of the candidate.
    """
    matched = text[start:end]
    window = text[max(0, start - 20):min(len(text), end + 30)]
    if canonical == "PA" or alias.lower() in {"pa", "pa-c", "pa c"}:
        # only PA-C or Physician Assistant — bare PA is too often a state
        if re.fullmatch(r"(?i)pa", matched):
            return False
        if not re.search(r"(?i)physician\s+assistant|pa-?c\b", window):
            if alias.lower() not in {"physician assistant", "pa-c", "pa c"}:
                return False
    if re.fullmatch(r"(?i)jd", matched):
        if re.search(r"(?i)jd\s*(?:edwards|finish|com\b)|jd\.com", window):
            return False
    if canonical in {"RN", "LPN", "CNA", "NP", "LVN"}:
        left = text[max(0, start - 70):start]
        if _CERT_SUPERVISION_LEFT_RE.search(left):
            return False
        # also "supervision of an RN or LPN" when match is the second credential
        wider = text[max(0, start - 90):min(len(text), end + 15)]
        if re.search(
            r"(?i)(?:under\s+(?:the\s+)?(?:direct\s+)?supervision\s+of|"
            r"supervised\s+by|reports?\s+to|reporting\s+to).{0,50}"
            + re.escape(matched),
            wider,
        ):
            return False
    return True


def extract_cert_records(text: str, *, title: str | None = None) -> list[dict]:
    """Cert/license mentions from JD body. Title-only hits are tagged, not required.

    Title containing 'RN' does NOT imply an RN license requirement.
    """
    rows = []
    body = normalize_jd_text(text) if isinstance(text, str) else ""
    title = normalize_jd_text(title) if isinstance(title, str) else ""

    for canonical, aliases in CERT_DICT.items():
        patterns = [canonical] + list(aliases)
        # drop bare "PA" / "JD" from alias list — too noisy
        if canonical == "PA":
            patterns = [p for p in patterns if p.lower() not in {"pa"}]
        body_hit = False
        for alias in sorted(set(patterns), key=len, reverse=True):
            if not alias or len(alias) < 2:
                continue
            pat = re.compile(rf"(?<!\w){re.escape(alias)}(?!\w)", re.I)
            for m in pat.finditer(body):
                if not _cert_alias_ok(canonical, alias, body, m.start(), m.end()):
                    continue
                window = body[max(0, m.start() - 40):m.end() + 40]
                required = bool(CERT_REQUIRE_CUE.search(window))
                rows.append({
                    "certification": canonical,
                    "matched_text": body[m.start():m.end()],
                    "source_field": "summary",
                    "cert_status": "required" if required else "mentioned",
                    "evidence": re.sub(r"\s+", " ", window).strip()[:250],
                    "char_start": m.start(),
                    "char_end": m.end(),
                })
                body_hit = True
            if body_hit:
                break

        if body_hit:
            continue
        for alias in sorted(set(patterns), key=len, reverse=True):
            if not alias or len(alias) < 2:
                continue
            pat = re.compile(rf"(?<!\w){re.escape(alias)}(?!\w)", re.I)
            m = pat.search(title)
            if m and _cert_alias_ok(canonical, alias, title, m.start(), m.end()):
                rows.append({
                    "certification": canonical,
                    "matched_text": m.group(0),
                    "source_field": "title",
                    "cert_status": "title_mention",
                    "evidence": title[:250],
                    "char_start": None,
                    "char_end": None,
                })
                break
    return rows


# ---------------------------------------------------------------------------
# Summary context filters (key off RAW skill name; ±8 word window)
# ---------------------------------------------------------------------------
_BENEFIT_WORDS_RE = re.compile(
    r"(?i)\b(?:dental|vision|medical|insurance|401\s*\(?\s*k\)?|life|disability|pto|"
    r"paid\s+time\s+off|referral\s+services?|ad&d|health\s+coverage|coverage)\b"
)


def _window_pm_words(text: str, start: int, end: int, radius: int = 8) -> str:
    tokens = list(re.finditer(r"\S+", text))
    if not tokens:
        return text
    # find token index covering start
    idx = 0
    for i, t in enumerate(tokens):
        if t.start() <= start < t.end() or t.start() >= start:
            idx = i
            break
        idx = i
    a = max(0, idx - radius)
    b = min(len(tokens), idx + radius + 1)
    return " ".join(t.group(0) for t in tokens[a:b])


def benefits_context_hit(matched: str, section_text: str, start: int | None = None, end: int | None = None) -> bool:
    """True if match sits near benefit words (±8 tokens or same sentence) — drop skill hit."""
    if not section_text:
        return False
    mt = matched or ""
    skillish = bool(re.search(
        r"(?i)\b(?:dental|vision|medical|insurance|event\s+planning|hospitality|healthcare)\b",
        mt,
    ))
    if not skillish and not re.search(r"(?i)\bevent\s+planning\b", mt):
        # still allow if window is clearly a benefits list containing the match
        skillish = True
    if start is not None and end is not None:
        win = _window_pm_words(section_text, start, end, radius=8)
        # also take sentence
        left = max(section_text.rfind(".", 0, start), section_text.rfind("\n", 0, start), 0)
        right = section_text.find(".", end)
        if right < 0:
            right = len(section_text)
        sent = section_text[left:right]
    else:
        win = section_text
        sent = section_text
    if _BENEFIT_WORDS_RE.search(win) or _BENEFIT_WORDS_RE.search(sent):
        return True
    if re.search(r"(?i)\breferral\s+services?\b", sent) and re.search(r"(?i)event\s+planning", mt):
        return True
    return False


def context_filter_skill(
    skill: str,
    matched: str,
    section_text: str,
    full_summary: str,
    *,
    char_start: int | None = None,
    char_end: int | None = None,
    company: str | None = None,
    job_title: str | None = None,
) -> str | None:
    """Return drop reason or None. Uses RAW skill name (e.g. Supervision), ±8 words."""
    text = section_text or full_summary or ""
    mt = matched or ""
    if char_start is not None and char_end is not None and text:
        # offsets relative to section_text when provided
        local_s = char_start if char_start < len(text) else 0
        local_e = min(char_end, len(text)) if char_end else local_s + len(mt)
        window = _window_pm_words(text, local_s, local_e, radius=8)
    else:
        # fall back: search matched in text
        idx = text.lower().find(mt.lower()) if mt else -1
        window = _window_pm_words(text, idx, idx + len(mt), radius=8) if idx >= 0 else text[:200]

    skill_l = (skill or "").lower()
    mt_l = mt.lower()
    base = re.sub(r"\s*\((?:unspecified|conflict)\)$", "", skill or "", flags=re.I).strip().lower()

    # company-name token only (do NOT drop when skill appears in job title —
    # e.g. "Salesforce" in "IT Specialist – Salesforce" is a real requirement)
    if company and base and len(base) >= 4:
        if re.search(rf"(?i)(?<!\w){re.escape(base)}(?!\w)", str(company)):
            return "context: company_title token"

    # corporate values / about-us boilerplate — only drop soft/generic tokens
    if re.search(
        r"(?i)\b(?:our values|our covenants|core of which are|more than just words|"
        r"heart and soul of everything|relentless adherence to our values|"
        r"operate through five global businesses|shaping tomorrow together)\b",
        window + " " + (full_summary[max(0, (char_start or 0) - 120):(char_end or 0) + 120] if full_summary else ""),
    ):
        if base in {
            "teamwork", "integrity", "leadership", "innovation", "sustainability",
            "quality", "safety", "culture", "ethics", "relationships", "people",
            "engineering", "security", "project management", "manufacturing",
        } or "unspecified" in skill_l:
            return "context: company values boilerplate"

    # benefits neighborhood (Event Planning / Dentistry / Insurance / Healthcare etc.)
    if benefits_context_hit(mt, text, char_start, char_end):
        return "context: benefits neighborhood"

    # company-name style: "Aimbridge Hospitality"
    if skill_l == "hospitality" and re.search(r"(?i)\b[A-Z][A-Za-z0-9&.'-]+\s+Hospitality\b", window):
        return "context: company name Hospitality"

    # supervision (raw name may be Supervision before merge → Team Management)
    if skill_l in {"supervision", "team management"} and "supervision" in mt_l:
        if re.search(
            r"(?i)\b(?:under|with)?\s*(?:direct|general|close)?\s*supervision\b|"
            r"\b(?:minimal|little|no|without)\s+supervision\b|"
            r"\bunder\s+(?:the\s+)?(?:direct\s+|general\s+|close\s+)?supervision\b",
            window,
        ):
            return "context: under/minimal supervision"

    if skill_l == "transportation":
        if re.search(r"(?i)\b(?:reliable|own|personal|have)\s+transportation\b", window):
            return "context: reliable/own transportation"

    if skill_l in {"presentation skills", "presentation"} or "presentation" in mt_l:
        if re.search(
            r"(?i)\b(?:food|merchandise|product|plate|visual)\s+presentations?\b",
            window,
        ):
            return "context: food/merchandise presentation"

    if skill_l in {"recruitment", "hiring"}:
        if re.search(
            r"(?i)\b(?:hiring|recruitment)\s+process\b|"
            r"\b(?:we are|currently|now)\s+recruiting\b|"
            r"\bthis\s+recruitment\s+is\s+open\b|"
            r"\brecruitment\s+agency\b|\brecruitment\s+are\s+acting\b|"
            r"\bequal\s+opportunity\b|\breasonable\s+accommodation\b|"
            r"\baccessibility\b|\bupon\s+hiring\b|\bafter\s+hiring\b",
            window,
        ):
            return "context: recruitment/hiring process or EEO"
        if "@" in window or re.search(r"(?i)\.com\b", window):
            return "context: email/url recruitment"
        # Keep only hiring-function cues; bare "recruitment" elsewhere is noise
        if not re.search(
            r"(?i)\b(?:recruit(?:ing)?\s+candidates|talent\s+acquisition|"
            r"sourcing\s+(?:candidates|talent)|full[- ]cycle\s+recruiting|"
            r"recruitment\s+(?:experience|skills|of\s+staff)|"
            r"experience\s+(?:in|with)\s+recruitment|"
            r"interviewing\s+(?:candidates|applicants)|"
            r"candidate\s+sourcing)\b",
            window,
        ):
            return "context: recruitment not hiring-function"

    if skill_l == "driving":
        if re.search(
            r"(?i)\bdriving\s+(?:excellence|results|growth|innovation|performance|change)\b|"
            r"\bdriv(?:e|ing)\s+(?:business|revenue|sales)\b",
            window,
        ):
            return "context: metaphorical driving"

    if skill_l == "nursing":
        if re.search(
            r"(?i)\b(?:college|school)\s+of\s+nursing\b|"
            r"\btravel\s+nursing\b|\bnursing\s+home\b|"
            r"\bnursing\s+(?:inc|llc|ltd|corp|services)\b",
            window,
        ):
            return "context: nursing school/home/company"

    if skill_l == "communication" and re.search(
        r"(?i)\bcommunication\s+(?:standards?|protocols?)\b", window
    ):
        return "context: communication standards/protocols"

    # Sense / not-requirement tightenings
    if skill_l in {"equity", "diversity and inclusion"} and re.search(
        r"(?i)\b(?:equal\s+opportunity|eeo|dei\b|diversity|inclusion|belonging|"
        r"protected\s+(?:class|characteristic)|affirmative\s+action)\b",
        window + " " + (full_summary[:400] if full_summary else ""),
    ):
        return "context: DEI/equity statement"

    if skill_l == "healthcare" and not re.search(
        r"(?i)\b(?:experience\s+in\s+healthcare|healthcare\s+experience|"
        r"clinical\s+healthcare|healthcare\s+(?:setting|background|industry)\b)",
        window,
    ):
        # bare sector word / company blurb
        if re.search(r"(?i)\bhealthcare\b", mt_l):
            return "context: healthcare sector word"

    if skill_l == "professionalism" and re.search(
        r"(?i)\bprofessional\s+development\b", window
    ):
        return "context: professional development benefit"

    if skill_l in {"counseling", "counselling"} and re.search(
        r"(?i)\b(?:employee\s+counselling|eap\b|employee\s+assistance|"
        r"benefits?\s+counselling)\b",
        window,
    ):
        return "context: HR employee counseling"

    if skill_l in {"management", "management (unspecified)"} and re.search(
        r"(?i)\b(?:time|case|account|pain|conflict|change|product|project|"
        r"inventory|revenue|risk)\s+management\b",
        window,
    ):
        return "context: management fragment of compound phrase"

    if skill_l in {"quality", "quality (unspecified)"} and re.search(
        r"(?i)\b(?:high[- ]quality|quality\s+of\s+life|air\s+quality|"
        r"water\s+quality|quality\s+improvement)\b",
        window,
    ):
        return "context: quality fragment/non-skill"

    if skill_l == "assessment" and re.search(
        r"(?i)\b(?:risk\s+assessment|evaluation\s*:|self[- ]assessment)\b",
        window,
    ):
        return "context: assessment wrong sense"

    if skill_l in {"human resources", "recruitment", "hiring"} and re.search(
        r"(?i)\b(?:hr\s+department|human\s+resources\s+department|"
        r"contact\s+(?:hr|human\s+resources)|upon\s+hiring|after\s+hiring)\b",
        window,
    ):
        return "context: HR department / upon hiring"

    if skill_l in {"software", "procedures"}:
        return "context: always_drop bare token"

    return None


def extract_certs(text: str, title: str | None = None) -> list[str]:
    """Canonical certs that are required/mentioned in body — excludes title-only."""
    recs = extract_cert_records(text, title=title)
    out = []
    seen = set()
    for r in recs:
        if r["source_field"] == "title":
            continue
        if r["certification"] not in seen:
            seen.add(r["certification"])
            out.append(r["certification"])
    return out


def skills_extraction_status(
    *,
    has_skills_text: bool,
    has_summary_text: bool,
    n_skills: int,
    n_raw_tokens: int = 0,
    n_unmapped_tokens: int = 0,
) -> str:
    """no_text / unmapped_only / all_filtered / ok. Null semantics: n_skills=0 ≠ no skills needed."""
    if n_skills > 0:
        return "ok"
    if not has_skills_text and not has_summary_text:
        return "no_text"
    if n_unmapped_tokens > 0 and n_raw_tokens > 0:
        return "unmapped_only"
    if n_raw_tokens > 0:
        return "all_filtered"
    # had summary but nothing mapped / no NER tokens
    if has_summary_text or has_skills_text:
        return "all_filtered"
    return "no_text"
