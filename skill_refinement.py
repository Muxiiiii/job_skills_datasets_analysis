"""
Post-extraction skill refinement helpers (evidence, job family, sense, hierarchy).

Round-3 fixes (Claude review):
- job_family stem regexes + safer abbrevs
- engineer split software vs non-software (no variable-width lookbehind)
- sense scoring via local window; drop non-skill security usages
- evidence sentence split on bare newlines; boilerplate strip
"""

from __future__ import annotations

import re
from typing import Optional, Tuple

# ---------------------------------------------------------------------------
# Job family (order matters — first match wins)
# ---------------------------------------------------------------------------
JOB_FAMILY_RULES = [
    ("Nursing & Clinical",
     r"\b(?:nurses?|nursing|registered nurses?|\brns?\b|lpns?|cnas?|nurse practitioners?|\bnps?\b|icu|med[- ]surg|clinical nurses?)\b"),
    ("Veterinary",
     r"\b(?:veterinar\w*|vet(?:erinary)?(?:\s+techs?|\s+surgeons?)?|animal care)\b"),
    # Psychiatrists are physicians (round6); keep psychology/therapy in Behavioral Health
    ("Physician & PA",
     r"\b(?:physicians?|doctors?|surgeons?|hospitalists?|psychiatrists?|"
     r"anesthesiologists?|obstetricians?|gynecologists?|cardiologists?|"
     r"physician assistants?|pa-c\b)\b"),
    ("Behavioral Health",
     r"\b(?:psycholog\w*|social workers?|behavioral health|"
     r"mental health(?:\s+therap\w*)?|marriage and family therap\w*|psychotherap\w*|"
     r"peer\s+support|therapists?|clinicians?|"
     r"(?:mental|behavioral|substance|clinical|licensed)\s+(?:health\s+)?(?:counselors?|counsellors?))\b"),
    # bare Counselor without clinical cue → Education (below) or Other
    ("Allied Health",
     r"\b(?:occupational therap\w*|physical therap\w*|respiratory therap\w*|phlebotom\w*|"
     r"radiolog\w*|sonograph\w*|dental hygien\w*|dentists?|hygienists?)\b"),
    ("Imaging & Radiology",
     r"\b(?:radiology|radiologic|ct tech|mri tech|ultrasound|x-?ray|imaging|technologists?)\b"),
    ("Lab & Science",
     r"\b(?:laboratory|lab techs?|scientists?|chemists?|biologists?|research associates?)\b"),
    ("Pharmacy",
     r"\b(?:pharmacists?|pharmacy(?:\s+technicians?)?|pharm techs?)\b"),
    ("Protective Services",
     r"\b(?:security officers?|security guards?|loss prevention|police|"
     r"corrections officers?|campus\s+safety|safety\s+officers?|ses\s+supervisor)\b"),
    ("Personal Care",
     r"\b(?:hair stylists?|cosmetolog\w*|barbers?|estheticians?|caregivers?|home\s+care)\b"),
    ("Architecture & Design",
     r"\b(?:architects?|architectural|interior design)\b"),
    ("Inspection & QA",
     r"\b(?:inspectors?|quality inspectors?|eddy\s+current|ndt\b|certifying\s+agent)\b"),
    ("Data & Analytics",
     r"\b(?:data analysts?|data scientists?|business intelligence|\bbi\b|data engineers?|"
     r"statisticians?|machine learning engineers?)\b"),
    ("Business Analyst",
     r"\b(?:business analysts?|systems analysts?|product analysts?|"
     r"business\s+process\s+consultants?|itam)\b"),
    ("Software & IT Engineering",
     r"\b(?:software(?:\s+engineers?)?|developers?|programmers?|devops|sre\b|full[- ]stacks?|"
     r"backends?|frontends?|java developers?|python developers?|qa engineers?|test engineers?|"
     r"test leads?|security engineers?|cloud engineers?|site reliability|sql server|"
     r"database administrators?|\bdbas?\b|mlops|platform engineers?|infrastructure engineers?)\b"),
    ("IT & Cybersecurity",
     r"\b(?:cyber\w*|information security|security analysts?|network admins?|sysadmins?|"
     r"system admins?|help desks?|desktop support|it support|systems engineers?|"
     r"network engineers?|\bnetwork\b.*\bengineer|infrastructure\b|\bplatform\b|"
     r"it\s+specialists?|salesforce|o365|office\s+365|information\s+technology)\b"),
    ("Engineering (Non-software)",
     r"\b(?:electrical|mechanical|civil|structural|controls|process|chemical|industrial|"
     r"robotics|environmental|geotechnical|maintenance\s+and\s+reliability)\s+"
     r"(?:engineers?|managers?)?\b|"
     r"\bengineering associates?\b|\bbiopharma\b|\bengineers?\b|\bengineering\b"),
    ("Project / Product Mgmt",
     r"\b(?:project managers?|\bpms?\b|program managers?|product managers?|scrum masters?|product owners?)\b"),
    ("Finance & Accounting",
     r"\b(?:accountants?|accounting|financial analysts?|budget analysts?|auditors?|\bcpas?\b|"
     r"bookkeep\w*|payroll|fp&a|accounts payable|accounts receivable|"
     r"finance managers?|billing|tax\s+advisory|national\s+tax)\b|"
     r"\bcontrollers?\b"),
    ("Risk & Compliance",
     r"\b(?:risk analysts?|compliance analysts?|\bbsa\b|\baml\b|fraud analysts?|"
     r"intelligence analysts?|site\s+safety\s+managers?|safety\s+managers?)\b"),
    ("Quality Analyst",
     r"\b(?:quality analysts?)\b"),
    ("Retail Ops",
     r"\b(?:retail|store managers?|cashiers?|merchandis\w*|loss prevention|"
     r"sales\s+associates?|district\s+sales\s+manager|store\s+sales|"
     r"guest\s+advisors?|product\s+demonstrators?|meat\s+managers?|"
     r"hourly\s+supervisor)\b"),
    ("Sales",
     r"\b(?:sales|account executives?|account managers?|business development|\bbdrs?\b|\bsdrs?\b)\b"),
    ("Marketing",
     r"\b(?:marketing|brand managers?|content strateg\w*|growth marketers?|"
     r"content executives?)\b"),
    ("HR",
     r"\b(?:human resources?|human resource managers?|\bhr\b|recruiters?|"
     r"talent acquisition|people partners?)\b"),
    ("Hospitality & Food",
     r"\b(?:restaurants?|chefs?|cooks?|bartenders?|hospitality|hotels?|deli|"
     r"kitchen|culinary|food\s+service|catering|bakers?|baristas?|"
     r"rooms?\s+managers?|shift\s+managers?|lunchroom)\b|"
     r"\bservers?\b"),
    ("Supply Chain & Ops",
     r"\b(?:supply chain|logistics|warehouses?|inventory|procurement|"
     r"operations managers?|planners?|distribution|fulfillment|"
     r"truck\s+drivers?|cdl\b|production\s+(?:operatives?|supervisors?)|"
     r"ramp\s+supervisors?|printing\s+supervisors?|production\s+managers?)\b"),
    ("Construction & Trades",
     r"\b(?:construction|electricians?|plumbers?|hvac|carpenters?|welders?|"
     r"forem[ae]n|estimators?|journeyperson|309a|site\s+supervisor|"
     r"es&h|ehs\s+manager|environmental\s+health|crushing|shop\s+supervisors?|"
     r"electrical\s+shop|airport\s+services?)\b"),
    ("Legal",
     r"\b(?:attorneys?|lawyers?|paralegals?|legal counsel|litigation|solicitors?)\b"),
    ("Education",
     r"\b(?:teachers?|instructors?|professors?|tutors?|tutoring|curriculum|"
     r"school principals?|lecturers?|elementary|"
     r"school\s+counselors?|admissions?\s+counselors?|guidance\s+counselors?)\b"),
    ("Customer Support",
     r"\b(?:customer service|customer support|call centers?|helpdesks?)\b"),
    ("Administrative",
     r"\b(?:administrative|office managers?|executive assistants?|receptionists?|clerks?|"
     r"medical assistants?|administrative assistants?)\b"),
    ("Data & Analytics",
     r"\b(?:analysts?)\b"),
    ("Management General",
     r"\b(?:managers?|directors?|supervisors?|leads?)\b"),
]

JOB_FAMILY_COMPILED = [(fam, re.compile(pat, re.I)) for fam, pat in JOB_FAMILY_RULES]

# Rules treated as broad fallbacks (coverage, not high precision)
_FALLBACK_FAMILIES = {"Management General", "Data & Analytics"}  # late "analysts?" rule is fallback-ish
_FALLBACK_RULE_IDX = {
    i for i, (fam, _) in enumerate(JOB_FAMILY_RULES)
    if fam == "Management General" or (fam == "Data & Analytics" and "analysts?" in JOB_FAMILY_RULES[i][1] and "data analysts" not in JOB_FAMILY_RULES[i][1])
}

# Negative filters applied after a candidate match
_FAMILY_NEGATIVES = {
    "Physician & PA": re.compile(r"(?i)(?:,\s*MD\b|,\s*PA\b|\bAnnapolis\b|\bMaryland\b|\bPennsylvania\b)"),
    "Hospitality & Food": re.compile(r"(?i)\bsql\s+server|servers?\s+(?:admin|engineer|developer)|server\s+dba"),
    "Finance & Accounting": re.compile(r"(?i)\b(?:air\s+traffic|traffic)\s+controller|controls?\s+engineer"),
}


def assign_job_family_detailed(title: Optional[str]) -> dict:
    """Return family + which rule fired + status (matched/fallback/other)."""
    empty = {
        "job_family": "Other",
        "job_family_rule": None,
        "job_family_status": "other",
    }
    if not isinstance(title, str) or not title.strip():
        return empty

    title_norm = title
    for idx, (fam, cre) in enumerate(JOB_FAMILY_COMPILED):
        if not cre.search(title_norm):
            continue
        neg = _FAMILY_NEGATIVES.get(fam)
        if neg and neg.search(title_norm):
            continue
        if fam == "Hospitality & Food" and re.search(r"(?i)sql|dba|database", title_norm):
            continue
        if fam == "Finance & Accounting" and re.search(r"(?i)traffic|controls?\s+engineer", title_norm):
            continue

        # Late bare "analysts?" rule index — mark fallback
        rule_pat = JOB_FAMILY_RULES[idx][1]
        is_fallback = (
            fam == "Management General"
            or (fam == "Data & Analytics" and rule_pat.strip() == r"\b(?:analysts?)\b")
            or (fam == "Engineering (Non-software)" and r"\bengineers?\b" in rule_pat and "electrical" in rule_pat)
        )
        # Non-software rule ends with bare engineers?|engineering — treat as fallback when
        # only the bare engineer part matched (no discipline adjective)
        if fam == "Engineering (Non-software)":
            if not re.search(
                r"(?i)\b(?:electrical|mechanical|civil|structural|controls|process|chemical|"
                r"industrial|robotics|environmental|geotechnical)\s+engineers?\b|"
                r"\bengineering associates?\b",
                title_norm,
            ):
                is_fallback = True

        status = "fallback" if is_fallback else "matched"
        return {
            "job_family": fam,
            "job_family_rule": f"{idx}:{fam}",
            "job_family_status": status,
        }
    return empty


def assign_job_family(title: Optional[str]) -> str:
    return assign_job_family_detailed(title)["job_family"]


# ---------------------------------------------------------------------------
# Drop non-skill security contexts
# ---------------------------------------------------------------------------
SECURITY_DROP_RE = re.compile(
    r"(?i)\bsocial security\b|\bsecurity clearance\b|\bjob security\b|"
    r"\bbackground check\b|\bdrug tests?\b|\bsecurity interview\b|"
    r"\bcredit check\b|\bsecurity number\b"
)

SENSES = {
    "Security": [
        ("Security Testing", r"(?i)\b(?:penetration|vulnerab\w*|owasp|appsec|security testing|sast|dast)\b"),
        ("Cybersecurity", r"(?i)\b(?:network security|cyber\w*|siem|firewall|infosec|encryption|endpoint|\biam\b|\bsoc\b|data protection)\b"),
        ("Physical Security", r"(?i)\b(?:guard|patrol|loss prevention|surveillance|cctv|security officer|security systems?|fire (?:alarm|safety)|access control)\b"),
        ("Financial Securities", r"(?i)\b(?:securities|trading|broker|capital markets?)\b"),
    ],
    "Quality": [
        ("Quality Assurance (Software)", r"(?i)\b(?:\bqa\b|defect|test automation|selenium|bugs?|software quality)\b"),
        ("Quality Control (Manufacturing)", r"(?i)\b(?:iso|six sigma|inspection|manufactur\w*|lean|production quality)\b"),
        ("Clinical Quality", r"(?i)\b(?:patient|clinical quality|joint commission|\bcms\b|nursing quality)\b"),
    ],
    "Management": [
        ("People Management", r"(?i)\b(?:direct reports?|people management|staff management|managing (?:a |the )?team|leadership of)\b"),
        ("Project Management", r"(?i)\b(?:project management|program management|\bpmp\b|waterfall|scrum|timeline|milestone)\b"),
        ("Operations Management", r"(?i)\b(?:operations management|ops management|store operations)\b"),
        ("Account / Case Management", r"(?i)\b(?:account management|case management|caseload|client portfolio)\b"),
        ("Fund Management", r"(?i)\b(?:fund management|portfolio management|asset management)\b"),
    ],
    "Operations": [
        ("IT Operations", r"(?i)\b(?:server|network|incident|uptime|\bsre\b|devops|infrastructure|it operations)\b"),
        ("Retail / Store Operations", r"(?i)\b(?:store|retail|merchandis\w*|cashier|floor operations)\b"),
        ("Business Operations", r"(?i)\b(?:business ops|operational excellence|\bsop\b|workflow)\b"),
        ("Clinical Operations", r"(?i)\b(?:patient|clinical|hospital|care delivery)\b"),
    ],
    "Analysis": [
        ("Data Analysis", r"(?i)\b(?:data analys\w*|\bsql\b|excel|dashboard|metrics?|analytics|tableau|power bi)\b"),
        ("Business Analysis", r"(?i)\b(?:requirements?|stakeholder|user stor\w*|business case|business analys\w*)\b"),
        ("Financial Analysis", r"(?i)\b(?:financial analys\w*|budget|forecast|variance|p&l|valuation)\b"),
        ("Clinical Analysis", r"(?i)\b(?:lab|specimen|diagnostic|clinical analys\w*)\b"),
    ],
    "Development": [
        ("Software Development", r"(?i)\b(?:software development|coding|programming|\bgit\b|\bapi\b|full[- ]stack|agile development)\b"),
        ("Business / Org Development", r"(?i)\b(?:business development|org(?:anizational)? development|talent development)\b"),
        ("Professional Development", r"(?i)\b(?:professional development|career development)\b"),
        ("Real Estate Development", r"(?i)\b(?:real estate|property development)\b"),
    ],
    "Training": [
        ("Employee Training / L&D", r"(?i)\b(?:employee training|staff training|onboard\w*|learning and development|l&d|facilita\w*)\b"),
        ("Technical / Product Training", r"(?i)\b(?:product training|technical training|certification training)\b"),
        ("Clinical Training", r"(?i)\b(?:clinical training|nursing education|precept\w*)\b"),
    ],
    "Safety": [
        ("Patient Safety", r"(?i)\b(?:patient safety|medication safety|fall prevention)\b"),
        ("Food Safety", r"(?i)\b(?:food safety|haccp|servsafe)\b"),
        ("Workplace / OSHA Safety", r"(?i)\b(?:osha|workplace safety|hazard|\bppe\b|\behs\b|environmental health|"
         r"safety\s+(?:procedures|practices|protocols|standards|program|policies|regulations|control)|"
         r"safe\s+work(?:place|ing)?(?:\s+environment)?|work\s+safely|company\s+safety)\b"),
    ],
}

# Ambiguous skills that still need duty-phrase recall from untyped / intro "other" sections
DUTY_RECALL_SKILLS = {
    "Documentation", "Reporting", "Driving", "Safety",
    "Leadership", "People Management", "Communication", "Teamwork",
}

GENERIC_SKILLS = set(SENSES.keys()) | {
    "Procedures", "Healthcare", "Business Administration", "Information Technology",
    "Engineering", "Finance", "Research", "Education", "Design", "Planning",
    "Coordination", "Project Coordination", "Implementation", "Monitoring",
    "Reporting", "Compliance", "Documentation", "Organization", "Leadership",
    "Teaching", "Strategic Planning", "Equipment Maintenance", "Diversity and Inclusion",
    "Testing", "Software", "Technical Skills",
    "Management (unspecified)", "Security (unspecified)", "Quality (unspecified)",
    "Operations (unspecified)", "Analysis (unspecified)", "Development (unspecified)",
    "Training (unspecified)", "Safety (unspecified)",
}

SENSE_META = {
    "Security Testing": ("hard", "Cloud & IT"),
    "Cybersecurity": ("hard", "Cloud & IT"),
    "Physical Security": ("hard", "Operations"),
    "Financial Securities": ("hard", "Finance & Accounting"),
    "Quality Assurance (Software)": ("hard", "Cloud & IT"),
    "Quality Control (Manufacturing)": ("hard", "Operations"),
    "Clinical Quality": ("hard", "Healthcare & Nursing"),
    "People Management": ("hard", "Management"),
    "Project Management": ("hard", "Management"),
    "Operations Management": ("hard", "Operations"),
    "Account / Case Management": ("hard", "Management"),
    "Fund Management": ("hard", "Finance & Accounting"),
    "IT Operations": ("hard", "Cloud & IT"),
    "Retail / Store Operations": ("hard", "Operations"),
    "Business Operations": ("hard", "Operations"),
    "Clinical Operations": ("hard", "Healthcare & Nursing"),
    "Data Analysis": ("hard", "Data & Analytics"),
    "Business Analysis": ("hard", "Management"),
    "Financial Analysis": ("hard", "Finance & Accounting"),
    "Clinical Analysis": ("hard", "Healthcare & Nursing"),
    "Software Development": ("hard", "Cloud & IT"),
    "Business / Org Development": ("hard", "Management"),
    "Professional Development": ("soft", "Professional Skills"),
    "Real Estate Development": ("hard", "Engineering & Construction"),
    "Employee Training / L&D": ("hard", "Management"),
    "Technical / Product Training": ("hard", "Management"),
    "Clinical Training": ("hard", "Healthcare & Nursing"),
    "Workplace / OSHA Safety": ("hard", "Operations"),
    "Patient Safety": ("hard", "Healthcare & Nursing"),
    "Food Safety": ("hard", "Operations"),
}


def _window_around(text: str, matched: Optional[str], radius: int = 8) -> str:
    """±radius tokens around matched_text; never include job title."""
    if not isinstance(text, str) or not text.strip():
        return ""
    if not matched:
        return text
    lower = text.lower()
    idx = lower.find(matched.lower())
    if idx < 0:
        return text
    tokens = re.findall(r"\S+", text)
    before = len(re.findall(r"\S+", text[:idx]))
    start = max(0, before - radius)
    end = min(len(tokens), before + radius + 1)
    return " ".join(tokens[start:end])


# NER compounds that must NOT collapse into Management / Development
COMPOUND_PRESERVE = {
    "fund management": "Fund Management",
    "portfolio management": "Fund Management",
    "asset management": "Fund Management",
    "agenda management": "Agenda Management",
    "full stack development": "Full Stack Development",
    "full-stack development": "Full Stack Development",
    "fullstack development": "Full Stack Development",
}

# sense names that are already concrete — skip further collapse
_CONCRETE_SENSE_NAMES = {s for senses in SENSES.values() for s, _ in senses} | set(COMPOUND_PRESERVE.values())


def refine_skill(
    skill: str,
    evidence: Optional[str],
    title: Optional[str],
    matched_text: Optional[str] = None,
    job_family: Optional[str] = None,
) -> Optional[str]:
    """Return refined skill, or None to DROP the row.

    Title is accepted for API compat but NEVER concatenated into the keyword window;
    job_family may add a light prior only.
    """
    result = refine_skill_detailed(skill, evidence, title, matched_text, job_family)
    if result is None:
        return None
    return result["skill_refined"]


def refine_skill_detailed(
    skill: str,
    evidence: Optional[str],
    title: Optional[str],
    matched_text: Optional[str] = None,
    job_family: Optional[str] = None,
) -> Optional[dict]:
    """Like refine_skill but also returns sense label (concrete / unspecified / conflict)."""
    mt = (matched_text or "").strip()
    mt_l = mt.lower()
    if mt_l in COMPOUND_PRESERVE:
        name = COMPOUND_PRESERVE[mt_l]
        return {"skill_refined": name, "sense": name}
    if skill in _CONCRETE_SENSE_NAMES or skill in COMPOUND_PRESERVE.values():
        return {"skill_refined": skill, "sense": skill}

    if skill == "Security":
        ctx_drop = f"{evidence or ''} {matched_text or ''}"
        if SECURITY_DROP_RE.search(ctx_drop):
            return None

    if skill not in SENSES:
        return {"skill_refined": skill, "sense": skill}

    window = _window_around(evidence or "", matched_text, radius=8)
    prior = job_family or ""

    scores = []
    for sense, pat in SENSES[skill]:
        score = 2 * len(re.findall(pat, window))
        if prior:
            score += len(re.findall(pat, prior))
        if skill == "Security" and job_family == "Protective Services" and sense == "Physical Security":
            score += 2
        if skill == "Security" and job_family == "Software & IT Engineering" and sense == "Cybersecurity":
            score += 1
        scores.append((score, sense))

    scores.sort(reverse=True)
    best = scores[0][0]
    second = scores[1][0] if len(scores) > 1 else 0
    if best <= 0:
        # Gold / Claude convention: bare workplace safety → Workplace / OSHA Safety
        if skill == "Safety":
            return {"skill_refined": "Workplace / OSHA Safety", "sense": "Workplace / OSHA Safety"}
        return {"skill_refined": f"{skill} (unspecified)", "sense": "unspecified"}
    hit = [s for sc, s in scores if sc > 0]
    if len(hit) > 1 and best == second:
        return {"skill_refined": f"{skill} (conflict)", "sense": "conflict"}
    if second > 0 and (best - second) <= 1 and best != second:
        if skill == "Safety":
            return {"skill_refined": "Workplace / OSHA Safety", "sense": "Workplace / OSHA Safety"}
        return {"skill_refined": f"{skill} (unspecified)", "sense": "unspecified"}
    return {"skill_refined": scores[0][1], "sense": scores[0][1]}


def meta_for_skill(skill: str, raw: str, skill_type_map: dict, domain_map: dict) -> Tuple[str, str]:
    if skill in SENSE_META:
        return SENSE_META[skill]
    if skill in domain_map or skill in skill_type_map:
        return skill_type_map.get(skill, "hard"), domain_map.get(skill, "Other")
    base = re.sub(r" \((?:unspecified|conflict)\)$", "", skill)
    if base in domain_map:
        return skill_type_map.get(base, "hard"), domain_map.get(base, "Other")
    return skill_type_map.get(raw, "hard"), domain_map.get(raw, "Other")


# ---------------------------------------------------------------------------
# Hierarchy
# ---------------------------------------------------------------------------
L2_BY_L3 = {
    "Quality Assurance (Software)": "Quality & Testing",
    "Quality Control (Manufacturing)": "Quality & Testing",
    "Clinical Quality": "Quality & Testing",
    "Quality Assurance": "Quality & Testing",
    "Quality": "Quality & Testing",
    "Quality (unspecified)": "Quality & Testing",
    "Quality (conflict)": "Quality & Testing",
    "Quality Improvement": "Quality & Testing",
    "Testing": "Quality & Testing",
    "Security Testing": "Quality & Testing",
    "Process Improvement": "Quality & Testing",
    "Cybersecurity": "Security",
    "Physical Security": "Security",
    "Financial Securities": "Security",
    "Security": "Security",
    "Security (unspecified)": "Security",
    "Security (conflict)": "Security",
    "Risk Management": "Security",
    "Data Analysis": "Data Analysis & BI",
    "Data Analysis (unspecified)": "Data Analysis & BI",
    "Data Visualization": "Data Analysis & BI",
    "Business Intelligence": "Data Analysis & BI",
    "SQL": "Data Analysis & BI",
    "Tableau": "Data Analysis & BI",
    "Power BI": "Data Analysis & BI",
    "Microsoft Excel": "Data Analysis & BI",
    "Statistics": "Data Analysis & BI",
    "Data Entry": "Data Analysis & BI",
    "Analysis": "Data Analysis & BI",
    "Analysis (unspecified)": "Data Analysis & BI",
    "Analysis (conflict)": "Data Analysis & BI",
    "Machine Learning": "Advanced Analytics",
    "Python": "Programming",
    "Java": "Programming",
    "JavaScript": "Programming",
    "C++": "Programming",
    "C#": "Programming",
    "Software Development": "Programming",
    "Full Stack Development": "Programming",
    "Development": "Programming",
    "Development (unspecified)": "Programming",
    "Development (conflict)": "Programming",
    "Software": "Programming",
    "Git": "Programming",
    "Version Control": "Programming",
    "Troubleshooting": "Programming",
    "Communication": "Communication & Collaboration",
    "Written Communication": "Communication & Collaboration",
    "Verbal Communication": "Communication & Collaboration",
    "Teamwork": "Communication & Collaboration",
    "Interpersonal Skills": "Communication & Collaboration",
    "Presentation Skills": "Communication & Collaboration",
    "Conflict Resolution": "Communication & Collaboration",
    "Customer Focus": "Communication & Collaboration",
    "Problem Solving": "Cognitive Skills",
    "Critical Thinking": "Cognitive Skills",
    "Decision Making": "Cognitive Skills",
    "Time Management": "Workplace Effectiveness",
    "Attention to Detail": "Workplace Effectiveness",
    "Adaptability": "Workplace Effectiveness",
    "Organization": "Workplace Effectiveness",
    "Multitasking": "Workplace Effectiveness",
    "Scheduling": "Workplace Effectiveness",
    "Accountability": "Workplace Effectiveness",
    "Professionalism": "Workplace Effectiveness",
    "Confidentiality": "Workplace Effectiveness",
    "Initiative": "Workplace Effectiveness",
    "People Management": "People Leadership",
    "Project Management": "Project & Product",
    "Product Management": "Project & Product",
    "Agile": "Project & Product",
    "Scrum Master": "Project & Product",
    "Leadership": "People Leadership",
    "Team Management": "People Leadership",
    "Management": "People Leadership",
    "Management (unspecified)": "People Leadership",
    "Management (conflict)": "People Leadership",
    "Fund Management": "Investment & Portfolio",
    "Agenda Management": "Workplace Effectiveness",
    "Coaching": "People Leadership",
    "Recruitment": "People Leadership",
    "Training": "People Leadership",
    "Training (unspecified)": "People Leadership",
    "Nursing": "Clinical Practice",
    "Patient Care": "Clinical Practice",
    "Medication Administration": "Clinical Practice",
    "Electronic Health Records": "Health IT",
    "HIPAA": "Health Compliance",
    "Infection Control": "Clinical Practice",
    "Mental Health": "Clinical Practice",
    "Counseling": "Clinical Practice",
    "Vital Signs": "Clinical Practice",
    "Care Planning": "Clinical Practice",
    "Healthcare": "Clinical Practice",
    "Sanitation": "Clinical Practice",
    "CPR": "Clinical Certifications",
    "BLS": "Clinical Certifications",
    "ACLS": "Clinical Certifications",
    "Sales": "Sales Execution",
    "Customer Service": "Sales Execution",
    "Marketing": "Go-to-Market",
    "Merchandising": "Retail Ops Skills",
    "Accounting": "Accounting & Bookkeeping",
    "Budgeting": "FP&A",
    "Financial Analysis": "FP&A",
    "Financial Modeling": "FP&A",
    "Inventory Management": "Supply Chain Ops",
    "Supply Chain": "Supply Chain Ops",
    "Manufacturing": "Production Ops",
    "Transportation": "Logistics",
    "Operations": "Business Ops",
    "Operations (unspecified)": "Business Ops",
    "Safety": "EHS & Safety",
    "Safety (unspecified)": "EHS & Safety",
    "Blueprints": "Trades & Drafting",
    "Electrical Systems": "Trades & Drafting",
    "Microsoft Office": "Productivity Tools",
    "Microsoft Word": "Productivity Tools",
    "Microsoft PowerPoint": "Productivity Tools",
    "Microsoft Outlook": "Productivity Tools",
    "Computer Proficiency": "Productivity Tools",
    "Mathematical Calculations": "Workplace Effectiveness",
    "Documentation": "Workplace Effectiveness",
}


# Skills that are concrete in certain job families (not generic there)
_FAMILY_CONCRETE = {
    "Sales": {"Sales"},
    "Marketing": {"Marketing", "Sales"},
    "Software & IT Engineering": {
        "Quality Assurance", "Quality Assurance (Software)", "Testing",
        "Software Development", "Software",
    },
    "IT & Cybersecurity": {"Cybersecurity", "Security Testing", "IT Operations"},
    "Nursing & Clinical": {"Nursing", "Patient Care", "Healthcare"},
    "Finance & Accounting": {"Accounting", "Financial Analysis", "Budgeting"},
}

_NEVER_GENERIC = {
    "Quality Assurance", "Quality Assurance (Software)", "Quality Control (Manufacturing)",
    "Clinical Quality", "Project Management", "Product Management", "Data Analysis",
    "Software Development", "Full Stack Development", "Fund Management",
    "Written Communication", "Cybersecurity", "Security Testing",
}


def skill_levels(skill_l3: str, course_domain: str, job_family: Optional[str] = None):
    """L2 falls back to '(unmapped)' — never copy L1."""
    l1 = course_domain or "Other"
    l2 = L2_BY_L3.get(skill_l3, "(unmapped)")
    if l2 == "(unmapped)":
        base = re.sub(r" \((?:unspecified|conflict)\)$", "", skill_l3)
        l2 = L2_BY_L3.get(base, "(unmapped)")

    base = re.sub(r" \((?:unspecified|conflict)\)$", "", skill_l3)
    is_generic = base in GENERIC_SKILLS or skill_l3.endswith("(unspecified)") or skill_l3.endswith("(conflict)")
    if skill_l3 in _NEVER_GENERIC or base in _NEVER_GENERIC:
        is_generic = False
    if job_family and base in _FAMILY_CONCRETE.get(job_family, set()):
        is_generic = False
    if skill_l3 == "Sales" and job_family != "Sales":
        is_generic = True
    return l1, l2, is_generic


# ---------------------------------------------------------------------------
# Alias tables + stage-4 pipeline (clean → merge → sense → hierarchy)
# ---------------------------------------------------------------------------
def load_alias_tables(path) -> dict:
    """Load skill_alias.csv → merge_map + hierarchy pairs (parent_skill, child_skill)."""
    import pandas as pd

    alias = pd.read_csv(path, comment="#")
    alias = alias.dropna(subset=["raw", "canonical", "action"])
    keep = set(alias.loc[alias["action"] == "keep", "raw"].astype(str))
    merge_map = {
        str(r): str(c)
        for r, c, a in alias[["raw", "canonical", "action"]].itertuples(index=False)
        if a == "merge" and str(r) not in keep
    }
    # parent action: raw = broad (parent_skill, dropped), canonical = specific (child_skill, kept)
    hierarchy = [
        (str(r), str(c))
        for r, c, a in alias[["raw", "canonical", "action"]].itertuples(index=False)
        if a == "parent"
    ]
    return {"merge_map": merge_map, "hierarchy": hierarchy, "keep": keep}


def _skill_matches_child(skill: str, child: str) -> bool:
    if skill == child:
        return True
    # sense-refined children still satisfy hierarchy (Quality Assurance (Software) ⊨ Quality Assurance)
    if skill.startswith(child + " ("):
        return True
    return False


def _skill_is_parent(skill: str, parent: str) -> bool:
    if skill == parent:
        return True
    if skill in {f"{parent} (unspecified)", f"{parent} (conflict)"}:
        return True
    return False


def apply_hierarchy_drops(df, hierarchy_pairs: list[tuple[str, str]], skill_col: str = "skill_refined"):
    """Drop broad parent_skill when a child_skill is present on the same job.

    Returns (kept_df, dropped_df with drop_reason).
    """
    import pandas as pd

    if df is None or len(df) == 0:
        empty = pd.DataFrame()
        return empty, empty

    have = df.groupby("job_link")[skill_col].apply(list).to_dict()
    drop_mask = []
    reasons = []
    for link, skill in zip(df["job_link"], df[skill_col]):
        skills = have.get(link, [])
        dropped = False
        reason = ""
        for parent, child in hierarchy_pairs:
            if not _skill_is_parent(skill, parent):
                continue
            if any(_skill_matches_child(s, child) for s in skills if s != skill):
                dropped = True
                reason = f"hierarchy: keep child '{child}', drop parent '{parent}'"
                break
        drop_mask.append(dropped)
        reasons.append(reason)

    dropped_df = df.loc[drop_mask].copy()
    if len(dropped_df):
        dropped_df["drop_reason"] = [r for r, m in zip(reasons, drop_mask) if m]
        dropped_df["parent_skill"] = dropped_df["drop_reason"].str.extract(r"drop parent '([^']+)'")
        dropped_df["child_skill"] = dropped_df["drop_reason"].str.extract(r"keep child '([^']+)'")
    kept = df.loc[[not m for m in drop_mask]].copy()
    return kept, dropped_df


def build_dedupe_candidates(js, min_freq: int = 5, name_sim_thresh: int = 85, co_thresh: float = 0.25):
    """Name-similar OR high-cooccurrence pairs for human review (no auto-merge)."""
    from itertools import combinations

    import pandas as pd

    try:
        from rapidfuzz import fuzz
    except ImportError:
        from difflib import SequenceMatcher

        class fuzz:
            @staticmethod
            def token_set_ratio(a, b):
                return int(100 * SequenceMatcher(None, a, b).ratio())

    vc = js["skill_refined"].value_counts() if "skill_refined" in js.columns else js["skill"].value_counts()
    skill_col = "skill_refined" if "skill_refined" in js.columns else "skill"
    skills_freq = vc[vc >= min_freq].index.tolist()
    jobs_of = js.groupby(skill_col)["job_link"].apply(set)

    # focus group always included if present
    focus = {
        "Management (unspecified)", "Management (conflict)", "Management",
        "Team Management", "People Management", "Leadership",
        "Quality Assurance", "Quality Assurance (Software)",
    }
    focus_present = [s for s in focus if s in jobs_of.index]

    cands = []
    pairs_seen = set()

    def _add(a, b, name_sim, co, reason):
        key = tuple(sorted((a, b)))
        if key in pairs_seen:
            return
        pairs_seen.add(key)
        ja, jb = jobs_of[a], jobs_of[b]
        cands.append({
            "a": a, "b": b, "name_sim": name_sim, "co_occur": round(co, 3),
            "n_a": len(ja), "n_b": len(jb), "reason": reason,
        })

    for a, b in combinations(skills_freq, 2):
        ja, jb = jobs_of[a], jobs_of[b]
        if not ja or not jb:
            continue
        co = len(ja & jb) / min(len(ja), len(jb))
        name_sim = fuzz.token_set_ratio(a.lower(), b.lower())
        if name_sim >= name_sim_thresh:
            _add(a, b, name_sim, co, "name_similar")
        elif co >= co_thresh:
            _add(a, b, name_sim, co, "high_cooccur")

    for a, b in combinations(focus_present, 2):
        ja, jb = jobs_of[a], jobs_of[b]
        co = len(ja & jb) / min(len(ja), len(jb)) if ja and jb else 0
        name_sim = fuzz.token_set_ratio(a.lower(), b.lower())
        _add(a, b, name_sim, co, "focus_group")

    return (
        pd.DataFrame(cands)
        .sort_values(["reason", "co_occur", "name_sim"], ascending=[True, False, False])
        .reset_index(drop=True)
    )


def refine_skill_table(
    evidence_or_job_skill,
    *,
    alias_tables: dict,
    skill_type_map: dict,
    domain_map: dict,
    title_by_link: Optional[dict] = None,
    family_by_link: Optional[dict] = None,
):
    """
    Stage-4 pipeline on evidence rows.

    Order: clean → merge → sense → hierarchy → aggregate (prefer has_evidence).
    Keeps ALL evidence until after sense; aggregation merges sources + evidence_ids.
    Dropped rows always land in skill_dropped with a reason (no silent deletes).
    """
    import pandas as pd

    df = evidence_or_job_skill.copy()
    n_before = len(df)
    title_by_link = title_by_link or {}
    family_by_link = family_by_link or {}
    merge_map = alias_tables["merge_map"]
    hierarchy = alias_tables["hierarchy"]

    if "evidence_id" not in df.columns:
        df["evidence_id"] = range(1, len(df) + 1)
    if "matched_text" in df.columns:
        df["skill_raw"] = df["matched_text"].fillna(df["skill"]).astype(str)
    else:
        df["skill_raw"] = df["skill"].astype(str)
    df["skill_canonical"] = df["skill"].astype(str)

    # 1) merge synonyms (+ round6 near-synonym canonicals)
    df["skill_canonical"] = df["skill_canonical"].replace(merge_map)
    df["skill_canonical"] = df["skill_canonical"].replace(CANONICAL_SKILL_MERGE)

    # 2) sense disambiguation — keep sense column
    refined, senses = [], []
    for skill, ev, mt, link in zip(
        df["skill_canonical"],
        df["evidence"] if "evidence" in df.columns else [None] * len(df),
        df["matched_text"] if "matched_text" in df.columns else [None] * len(df),
        df["job_link"],
    ):
        detail = refine_skill_detailed(skill, ev, title_by_link.get(link), mt, family_by_link.get(link))
        if detail is None:
            refined.append(None)
            senses.append(None)
        else:
            refined.append(detail["skill_refined"])
            senses.append(detail["sense"])
    df["skill_refined"] = refined
    df["sense"] = senses

    sense_dropped = df[df["skill_refined"].isna()].copy()
    if len(sense_dropped):
        sense_dropped["drop_reason"] = "sense: non-skill context"
        sense_dropped["parent_skill"] = None
        sense_dropped["child_skill"] = None
    df = df[df["skill_refined"].notna()].copy()

    # 3) hierarchy
    df, hier_dropped = apply_hierarchy_drops(df, hierarchy, skill_col="skill_refined")
    dropped_parts = [p for p in (sense_dropped, hier_dropped) if p is not None and len(p)]
    dropped = pd.concat(dropped_parts, ignore_index=True) if dropped_parts else pd.DataFrame()

    # 4) aggregate AFTER sense — prefer has_evidence; merge sources + evidence_ids
    #    (do NOT keep='first' which silently preferred NER)
    n_pre_agg = len(df)
    records = []
    n_merged_away = 0
    for (link, skill), g in df.groupby(["job_link", "skill_refined"], sort=False):
        sources = sorted(set(g["source_field"].tolist())) if "source_field" in g.columns else []
        eids = [str(x) for x in g["evidence_id"].tolist()]
        n_merged_away += max(0, len(g) - 1)
        has_ev = g["evidence_status"].eq("has_evidence") if "evidence_status" in g.columns else pd.Series([False] * len(g))
        status = "has_evidence" if bool(has_ev.any()) else "ner_only"
        row = g.loc[has_ev].iloc[0] if has_ev.any() else g.iloc[0]
        rec = row.to_dict()
        rec["sources"] = "|".join(sources)
        rec["evidence_ids"] = "|".join(eids)
        rec["n_evidence"] = int(len(g))
        rec["evidence_status"] = status
        if status != "has_evidence":
            rec["evidence"] = None
        records.append(rec)
    out = pd.DataFrame.from_records(records) if records else df.head(0).copy()

    # rows absorbed by aggregation → dropped log (not silent)
    if n_merged_away and len(df):
        # mark non-chosen evidence rows
        chosen_ids = set()
        for r in records:
            # primary evidence_id is the chosen row's id
            chosen_ids.add(str(r.get("evidence_id")))
        absorbed = df[~df["evidence_id"].astype(str).isin(chosen_ids)].copy()
        if len(absorbed):
            absorbed["drop_reason"] = "aggregate: merged into job-skill (kept sibling evidence_ids)"
            absorbed["parent_skill"] = None
            absorbed["child_skill"] = None
            dropped = pd.concat([dropped, absorbed], ignore_index=True) if len(dropped) else absorbed

    # 5) refresh metadata + ner unsupported / always-drop
    if len(out):
        types, domains, l1s, l2s, generics = [], [], [], [], []
        confidences = []
        keep_mask = []
        status_col = out["evidence_status"] if "evidence_status" in out.columns else ["has_evidence"] * len(out)
        sources_col = out["sources"] if "sources" in out.columns else [""] * len(out)
        for skill, raw, link, status, sources in zip(
            out["skill_refined"], out["skill_raw"], out["job_link"], status_col, sources_col
        ):
            base = re.sub(r" \((?:unspecified|conflict)\)$", "", str(skill))
            if base in ALWAYS_DROP_SKILLS or skill in ALWAYS_DROP_SKILLS:
                keep_mask.append(False)
                types.append(None); domains.append(None); l1s.append(None); l2s.append(None)
                generics.append(True); confidences.append("drop_always")
                continue
            t, d = meta_for_skill(skill, raw, skill_type_map, domain_map)
            fam = family_by_link.get(link)
            l1, l2, g = skill_levels(skill, d, fam)
            conf = "normal"
            types.append(t); domains.append(d); l1s.append(l1); l2s.append(l2)
            generics.append(g); confidences.append(conf); keep_mask.append(True)
        out["skill_type"] = types
        out["course_domain"] = domains
        out["skill_l1"] = l1s
        out["skill_l2"] = l2s
        out["skill_l3"] = out["skill_refined"]
        out["is_generic"] = generics
        out["confidence"] = confidences
        out["skill"] = out["skill_refined"]
        drop_idx = [i for i, k in enumerate(keep_mask) if not k]
        if drop_idx:
            dropped_always = out.iloc[drop_idx].copy()
            dropped_always["drop_reason"] = "always_drop: too_generic bare token"
            dropped_always["parent_skill"] = None
            dropped_always["child_skill"] = None
            dropped = pd.concat([dropped, dropped_always], ignore_index=True) if len(dropped) else dropped_always
        out = out.iloc[[i for i, k in enumerate(keep_mask) if k]].copy()

    out.attrs["n_before"] = n_before
    out.attrs["n_pre_agg"] = n_pre_agg
    out.attrs["n_merged_away"] = n_merged_away
    return out, dropped


# ---------------------------------------------------------------------------
# Section segmentation (stage 2) — tag then skip benefits/company/eeo for skills
# ---------------------------------------------------------------------------
# Headers only at line / bullet start, followed by ':' or newline (round4).
# Avoids mid-sentence "comprehensive benefits" / "other duties as assigned".
SECTION_HEADER = re.compile(
    r"(?im)(?:^|[\n\r•]\s*)("
    r"minimum qualifications|preferred qualifications|basic qualifications|"
    r"qualifications|requirements|what you(?:'ll)? bring|who you are|"
    r"skills (?:and|&) experience|education(?:\s+requirements?)?|"
    r"responsibilities|what you(?:'ll)? do|duties|essential functions|day to day|"
    r"benefits|perks|what we offer|compensation(?:\s+and\s+benefits)?|"
    r"about (?:us|the company|the role|the job)|who we are|our company|"
    r"our values|our covenants|company overview|who we(?:'re| are)|"
    r"equal opportunity|eeo|diversity(?:\s+and\s+inclusion)? statement|"
    r"how to apply|to apply"
    r")\s*(?::|(?=\n))"
)

_SECTION_TYPE_MAP = [
    (("preferred qualifications",), "preferred"),
    (("minimum qualifications", "basic qualifications", "qualifications", "requirements",
      "what you'll bring", "what youll bring", "what you bring", "who you are",
      "skills and experience", "skills & experience", "education", "education requirements"), "requirements"),
    (("responsibilities", "what you'll do", "what youll do", "what you do", "duties",
      "essential functions", "day to day", "about the role", "about the job"), "responsibilities"),
    (("benefits", "perks", "what we offer", "compensation"), "benefits"),
    (("about us", "about the company", "who we are", "our company", "our values",
      "our covenants", "company overview", "who we're", "who we are"), "company"),
    (("equal opportunity", "eeo", "diversity", "diversity and inclusion statement"), "eeo"),
    (("how to apply", "to apply"), "other"),
]

# Round6: summary evidence only from requirement-class sections when they exist.
# "other" kept as fallback only when the JD has no req/preferred/responsibilities headers.
SUMMARY_EVIDENCE_SECTIONS = {"requirements", "preferred", "responsibilities"}
SKILL_ALLOWED_SECTIONS = SUMMARY_EVIDENCE_SECTIONS | {"other"}

# Bare tokens that are never real skills (Claude: always too_generic)
ALWAYS_DROP_SKILLS = {"Software", "Procedures", "Healthcare", "Implementation"}

# High FP skills: keep from requirements / preferred / responsibilities only
# (round7: responsibilities == requirements; do NOT require requirements-only)
LOW_PRECISION_SUMMARY_ONLY = {
    "Recruitment", "Hiring", "Human Resources", "Management", "Management (unspecified)",
    "Payroll", "Counseling", "Transportation", "Procurement", "Professionalism",
    "Adaptability", "Manufacturing", "Organization", "Accountability", "Testing",
    "Equity", "Sustainability", "Integrity", "Teaching",
}
LOW_PRECISION_ALLOWED_SECTIONS = {"requirements", "preferred", "responsibilities"}

# Merge near-synonym canonical names (round6 recall)
CANONICAL_SKILL_MERGE = {
    "Team Management": "People Management",
}


def _header_to_section_type(header: str) -> str:
    h = header.lower().strip()
    for keys, stype in _SECTION_TYPE_MAP:
        if any(k in h for k in keys):
            return stype
    return "other"


def split_sections_typed(text: Optional[str]) -> list[dict]:
    """Return list of {section_type, header, text} covering the whole JD."""
    if not isinstance(text, str) or not text.strip():
        return []
    parts = []
    last_header, last_pos = "intro", 0
    last_type = "other"
    for m in SECTION_HEADER.finditer(text):
        chunk = text[last_pos:m.start()]
        if chunk.strip():
            parts.append({"section_type": last_type, "header": last_header, "text": chunk})
        last_header = m.group(1)
        last_type = _header_to_section_type(last_header)
        last_pos = m.end()
    tail = text[last_pos:]
    if tail.strip() or not parts:
        parts.append({"section_type": last_type, "header": last_header, "text": tail})
    return parts


def skill_extractable_text(text: Optional[str]) -> tuple[str, bool]:
    """Concatenate only sections allowed for skill extraction.

    Returns (text, has_req_or_resp_section).
    If no typed sections found / all empty, returns stripped boilerplate full text
    but with benefits/company/eeo removed via section filter when headers exist.
    """
    if not isinstance(text, str) or not text.strip():
        return "", False
    sections = split_sections_typed(text)
    allowed = [s["text"] for s in sections if s["section_type"] in SKILL_ALLOWED_SECTIONS]
    has_signal = any(
        s["section_type"] in {"requirements", "preferred", "responsibilities"}
        for s in sections
    )
    joined = "\n".join(allowed).strip()
    if joined:
        return joined, has_signal
    # no usable headers — strip known boilerplate blocks then return
    return strip_boilerplate(text).strip(), False


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------
SENT_SPLIT = re.compile(r"(?<=[.;!?•])\s+|\n+")

BOILERPLATE_RE = re.compile(
    r"(?is)(?:"
    r"equal opportunity(?:\s+employer)?.*?(?=\n\n|\Z)|"
    r"we are an equal opportunity.*?(?=\n\n|\Z)|"
    r"we prohibit discrimination.*?(?=\n\n|\Z)|"
    r"[^\n]{0,80}commitment to diversity[^\n]{0,200}.*?(?=\n\n|\Z)|"
    r"(?:benefits|perks|what we offer|compensation(?:\s+and\s+benefits)?)\s*:.*?(?=\n[A-Z][^\n]{0,40}:|\n\n|\Z)|"
    r"(?:how to apply|to apply|send (?:your )?cv|send resume).*?(?=\n\n|\Z)"
    r")"
)

# Non-skill usages — drop skill candidates when context matches
NON_SKILL_CONTEXT_RE = re.compile(
    r"(?i)\bsocial security\b|\bsecurity clearance\b|\bjob security\b|"
    r"\bbackground check\b|\bdrug tests?\b|\bsecurity interview\b|"
    r"\bcredit check\b|\bsecurity number\b|"
    r"\bequal opportunity\b|\bprohibit discrimination\b|"
    r"\bcommitment to diversity\b|\bdiversity in (?:its|our) workforce\b"
)


def strip_boilerplate(text: Optional[str]) -> str:
    if not isinstance(text, str):
        return ""
    return BOILERPLATE_RE.sub(" ", text)


def centered_snippet(text: str, start: int, end: int, max_len: int = 250) -> str:
    """Evidence centered on the match span; newlines collapsed (stage 3)."""
    if not text:
        return ""
    start = max(0, min(start, len(text)))
    end = max(start, min(end, len(text)))
    mid = (start + end) // 2
    half = max_len // 2
    a = max(0, mid - half)
    b = min(len(text), mid + half)
    # snap outward to whitespace when possible
    if a > 0:
        sp = text.rfind(" ", 0, a + 1)
        if sp != -1 and mid - sp < max_len:
            a = sp + 1
    if b < len(text):
        sp = text.find(" ", b - 1)
        if sp != -1 and sp - mid < max_len:
            b = sp
    snippet = text[a:b]
    return re.sub(r"\s+", " ", snippet).strip()


def find_evidence(summary: Optional[str], aliases: list[str], max_len: int = 250):
    """Legacy helper — prefer extract_skill_evidence() for new pipelines."""
    if not isinstance(summary, str) or not summary.strip():
        return None, None, None
    clean = strip_boilerplate(summary)
    for a in sorted(aliases, key=len, reverse=True):
        if not a:
            continue
        m = re.search(rf"(?<!\w){re.escape(a)}(?!\w)", clean, re.I)
        if m:
            return (
                clean[m.start():m.end()],
                centered_snippet(clean, m.start(), m.end(), max_len=max_len),
                m.start(),
            )
    return None, None, None


def find_evidence_from_ner(ner_cell: Optional[str], aliases: list[str]):
    if not isinstance(ner_cell, str):
        return None
    toks = [t.strip() for t in ner_cell.split(",") if t.strip()]
    alias_set = {a.lower() for a in aliases}
    for tok in toks:
        if tok.lower() in alias_set:
            return tok
    for a in sorted(aliases, key=len, reverse=True):
        if len(a) < 6 and " " not in a:
            continue
        for tok in toks:
            if re.fullmatch(rf"(?i){re.escape(a)}", tok):
                return tok
    return None


def build_alias_to_skill(skill_dict: dict) -> dict[str, str]:
    """Longer aliases win when the same string maps to multiple skills."""
    pairs: list[tuple[str, str]] = []
    for skill, aliases in skill_dict.items():
        pairs.append((skill.lower(), skill))
        for a in aliases:
            if a:
                pairs.append((a.lower(), skill))
    pairs.sort(key=lambda x: -len(x[0]))
    out: dict[str, str] = {}
    for al, sk in pairs:
        if al not in out:
            out[al] = sk
    return out


# Short / acronym aliases matched in summary with strict word boundaries (round4).
# Matched via regex (case-insensitive with \b), not dropped for being short.
SHORT_SUMMARY_ALIASES = {
    "sql", "aws", "cpr", "excel", "java", "hvac", "bls", "acls", "pals",
    "git", "etl", "crm", "seo", "cdl", "pmp", "cpa", "cfa", "ehr", "emr",
    "gaap", "hipaa", "osha", "html", "css", "api", "sre", "iam", "soc", "sap",
}
# Must match with exact casing (or exclude verb forms) — round5
SHORT_CASE_SENSITIVE = {"Excel", "Git", "CSS", "CRM", "SAP"}
_SHORT_VERB_EXCLUDE = re.compile(
    r"(?i)\b(?:to\s+)?excel\s+in\b|\beager\s+to\s+excel\b|\bexcel\s+at\b|"
    r"\bEIT\s+or\s+GIT\b|\bGIT\s+preferred\b"
)

# Sections where AMBIGUOUS_FOR_SUMMARY skills may be matched (then sense-scored)
AMBIGUOUS_ALLOWED_SECTIONS = {"requirements", "preferred", "responsibilities"}


def build_summary_keyword_processor(skill_dict: dict, ambiguous_for_summary: Optional[set] = None):
    """FlashText for multi-word / long aliases. Short + ambiguous handled separately."""
    from flashtext import KeywordProcessor

    ambiguous_for_summary = ambiguous_for_summary or set()
    kp = KeywordProcessor(case_sensitive=False)
    for canonical, aliases in skill_dict.items():
        # ambiguous singles go through section-gated regex, not flashtext-on-full-JD
        if canonical in ambiguous_for_summary:
            for a in aliases:
                if a and (" " in a or len(a) >= 8):
                    kp.add_keyword(a, canonical)
            continue
        for a in aliases:
            if not a:
                continue
            if a.lower() in SHORT_SUMMARY_ALIASES:
                continue  # regex path
            if " " in a or len(a) >= 6:
                kp.add_keyword(a, canonical)
    return kp


def _short_alias_hits(text: str, skill_dict: dict) -> list[tuple[str, int, int]]:
    """Strict word-boundary matches for short aliases (SQL / Excel / CPR / SAP)."""
    alias_map = {}
    for skill, aliases in skill_dict.items():
        for a in aliases:
            if a and a.lower() in SHORT_SUMMARY_ALIASES:
                alias_map.setdefault(a.lower(), skill)
        if skill.lower() in SHORT_SUMMARY_ALIASES:
            alias_map.setdefault(skill.lower(), skill)
    # Microsoft Excel etc.
    if "Microsoft Excel" in skill_dict:
        alias_map.setdefault("excel", "Microsoft Excel")
    hits = []
    for alias, skill in sorted(alias_map.items(), key=lambda x: -len(x[0])):
        # case-sensitive forms for verb-prone tokens
        if alias in {"excel", "git", "css", "crm", "sap"}:
            # require capitalised token (Excel / Git / …) OR all-caps
            pat = re.compile(rf"(?<![A-Za-z0-9])({re.escape(alias.capitalize())}|{re.escape(alias.upper())})(?![A-Za-z0-9])")
            for m in pat.finditer(text):
                # verb / acronym exclusions
                ctx = text[max(0, m.start() - 25):m.end() + 25]
                if alias == "excel" and re.search(r"(?i)\b(?:to\s+)?excel\s+(?:in|at)\b|\beager\s+to\s+excel\b", ctx):
                    continue
                if alias == "git" and re.search(r"(?i)\b(?:EIT|GIT)\b", ctx) and not re.search(r"(?i)\bgit\b", m.group(0)):
                    continue
                if alias == "git" and m.group(0) == "GIT" and re.search(r"(?i)\bEIT\b", ctx):
                    continue
                hits.append((skill, m.start(), m.end()))
        else:
            for m in re.finditer(rf"(?<![A-Za-z0-9]){re.escape(alias)}(?![A-Za-z0-9])", text, re.I):
                hits.append((skill, m.start(), m.end()))
    return hits


def _ambiguous_alias_hits(text: str, skill_dict: dict, ambiguous_for_summary: set) -> list[tuple[str, int, int]]:
    """Match ambiguous skills inside allowed section text only (caller gates section)."""
    hits = []
    for skill in ambiguous_for_summary:
        aliases = skill_dict.get(skill, [])
        # include canonical lowercased
        forms = sorted({skill.lower(), *[a.lower() for a in aliases if a]}, key=len, reverse=True)
        for a in forms:
            if len(a) < 4:
                continue
            for m in re.finditer(rf"(?<!\w){re.escape(a)}(?!\w)", text, re.I):
                hits.append((skill, m.start(), m.end()))
    return hits


def _section_spans(summary: str) -> list[tuple[str, str, int, int, str]]:
    """(section_type, header, start, end, chunk) covering the JD."""
    cursor = 0
    last_header, last_type = "intro", "other"
    spans = []
    for m in SECTION_HEADER.finditer(summary):
        chunk = summary[cursor:m.start()]
        if chunk.strip():
            spans.append((last_type, last_header, cursor, m.start(), chunk))
        last_header = m.group(1)
        last_type = _header_to_section_type(last_header)
        cursor = m.end()
    tail = summary[cursor:]
    if tail.strip() or not spans:
        spans.append((last_type, last_header, cursor, len(summary), tail))
    return spans


def _section_type_at(spans, pos: int) -> str:
    for stype, _h, a, b, _c in spans:
        if a <= pos < b:
            return stype
    return "other"


def extract_skill_evidence(
    job_skills: Optional[str],
    job_summary: Optional[str],
    skill_dict: dict,
    *,
    ambiguous_for_summary: Optional[set] = None,
    is_noise_fn=None,
    alias_to_skill: Optional[dict] = None,
    summary_kp=None,
    evidence_id_start: int = 1,
    context_filters=None,
    company: Optional[str] = None,
    job_title: Optional[str] = None,
) -> tuple[list[dict], list[dict]]:
    """
    Match-time evidence. Returns (evidence_rows, token_log_rows).

    - NER tokens → ner_only (no fabricated summary evidence)
    - Summary: long aliases via flashtext; short aliases via \\b; ambiguous only in
      requirements/preferred/responsibilities (then sense-scored later)
    """
    ambiguous_for_summary = ambiguous_for_summary or set()
    alias_to_skill = alias_to_skill or build_alias_to_skill(skill_dict)
    context_filters = context_filters or []
    rows: list[dict] = []
    token_log: list[dict] = []
    from extraction_resources import normalize_jd_text
    summary = normalize_jd_text(job_summary) if isinstance(job_summary, str) else ""
    has_eeo = bool(NON_SKILL_CONTEXT_RE.search(summary)) if summary else False
    eid = evidence_id_start
    spans_early = _section_spans(summary) if summary.strip() else []
    has_req_signal = any(
        st in SUMMARY_EVIDENCE_SECTIONS for st, *_ in spans_early
    ) if spans_early else False

    def _append_ev(**kwargs):
        nonlocal eid
        kwargs["evidence_id"] = eid
        eid += 1
        rows.append(kwargs)

    # --- NER cell ---
    if isinstance(job_skills, str) and job_skills.strip():
        pos = 0
        for raw_part in job_skills.split(","):
            tok = raw_part.strip()
            lead = len(raw_part) - len(raw_part.lstrip())
            tok_start = pos + lead
            tok_end = tok_start + len(tok)
            pos += len(raw_part) + 1
            if not tok:
                continue
            tok_l = tok.lower()
            if is_noise_fn and is_noise_fn(tok):
                token_log.append({"raw_token": tok, "status": "filtered", "reason": "noise"})
                continue
            if tok_l in {"diversity", "inclusion"}:
                token_log.append({"raw_token": tok, "status": "filtered", "reason": "eeo_token"})
                continue
            skill = alias_to_skill.get(tok_l)
            if not skill:
                token_log.append({"raw_token": tok, "status": "unmapped", "reason": ""})
                continue
            if skill in ALWAYS_DROP_SKILLS:
                token_log.append({"raw_token": tok, "status": "filtered", "reason": "always_drop"})
                continue
            if skill == "Diversity and Inclusion" and has_eeo and "diversity and inclusion" not in tok_l:
                token_log.append({"raw_token": tok, "status": "filtered", "reason": "eeo_context"})
                continue
            # Round6: ner_only without JD support → keep only if summary is thin;
            # otherwise drop high-risk generics / mark unsupported.
            jd_supported = False
            if summary.strip():
                aliases = skill_dict.get(skill, []) or []
                for al in list(aliases) + [skill, tok]:
                    if not al:
                        continue
                    if re.search(rf"(?i)(?<!\w){re.escape(str(al))}(?!\w)", summary):
                        jd_supported = True
                        break
            # Drop unsupported NER for generics / high-FP skills only (keep concrete NER
            # like Python/RN even when the JD uses a synonym we don't alias yet).
            base_tok_skill = re.sub(r" \((?:unspecified|conflict)\)$", "", skill)
            if (
                not jd_supported
                and len(summary.strip()) >= 200
                and (
                    skill in ALWAYS_DROP_SKILLS
                    or skill in GENERIC_SKILLS
                    or skill in ambiguous_for_summary
                    or skill in LOW_PRECISION_SUMMARY_ONLY
                    or base_tok_skill in LOW_PRECISION_SUMMARY_ONLY
                )
            ):
                token_log.append({
                    "raw_token": tok, "status": "filtered",
                    "reason": "ner_unsupported: no JD support",
                })
                continue
            token_log.append({"raw_token": tok, "status": "mapped", "reason": skill})
            _append_ev(
                skill=skill,
                source_field="job_skills",
                section_type="ner_cell",
                matched_text=tok,
                char_start=tok_start,
                char_end=tok_end,
                evidence=None,
                evidence_status="ner_only",
                rule_id=f"ner_alias:{skill}",
            )

    # --- Summary ---
    if summary.strip():
        if summary_kp is None:
            summary_kp = build_summary_keyword_processor(skill_dict, ambiguous_for_summary)
        spans = _section_spans(summary)
        hits: list[tuple[str, int, int, str]] = []  # skill, start, end, rule
        try:
            for item in summary_kp.extract_keywords(summary, span_info=True):
                if len(item) == 3:
                    hits.append((item[0], item[1], item[2], "summary_alias"))
        except TypeError:
            pass

        # short aliases on full text (section-filtered below)
        for skill, start, end in _short_alias_hits(summary, skill_dict):
            hits.append((skill, start, end, "summary_short"))

        # ambiguous: req/preferred/responsibilities; also untyped "other" (short JD)
        # and multi-word duty phrases anywhere in intro other (round7)
        for stype, _h, a, _b, chunk in spans:
            allow_amb = stype in AMBIGUOUS_ALLOWED_SECTIONS or (
                stype == "other" and not has_req_signal
            )
            if not allow_amb and stype == "other":
                # still scan duty-recall skills; keep gate applies matched_multi later
                amb_subset = ambiguous_for_summary & DUTY_RECALL_SKILLS
                if amb_subset:
                    for skill, s, e in _ambiguous_alias_hits(chunk, skill_dict, amb_subset):
                        hits.append((skill, a + s, a + e, "summary_ambiguous"))
                continue
            if not allow_amb:
                continue
            for skill, s, e in _ambiguous_alias_hits(chunk, skill_dict, ambiguous_for_summary):
                hits.append((skill, a + s, a + e, "summary_ambiguous"))

        seen_spans: set[tuple[str, int, int]] = set()
        for skill, start, end, rule in hits:
            owner = None
            for stype, header, a, b, chunk in spans:
                if a <= start < b:
                    owner = (stype, header, a, b, chunk)
                    break
            if owner is None:
                continue
            stype, header, a, b, chunk = owner
            if stype not in SKILL_ALLOWED_SECTIONS:
                continue
            matched = summary[start:end]
            matched_multi = (" " in matched.strip()) or (len(matched.strip()) >= 8)
            duty_other_ok = (
                skill in DUTY_RECALL_SKILLS
                and stype == "other"
                and matched_multi
                and rule in {"summary_alias", "summary_short", "summary_ambiguous"}
            )
            # Round6: when JD has req sections, drop "other" hits only for ambiguous /
            # generic bare tokens (keeps Communication/Teamwork etc. in prose).
            # Round7: keep multi-word duty phrases even in intro "other".
            if stype == "other" and has_req_signal and not duty_other_ok:
                if skill in ambiguous_for_summary or skill in ALWAYS_DROP_SKILLS or skill in GENERIC_SKILLS:
                    continue
            if skill in ALWAYS_DROP_SKILLS:
                token_log.append({
                    "raw_token": summary[start:end], "status": "filtered",
                    "reason": "always_drop", "skill": skill, "section_type": stype,
                })
                continue
            base_skill = re.sub(r" \((?:unspecified|conflict)\)$", "", skill)
            # Short / untyped JD: treat sole "other" blob as requirements (round7)
            effective_stype = stype
            if stype == "other" and (not has_req_signal or duty_other_ok):
                effective_stype = "requirements"
            if (
                (skill in LOW_PRECISION_SUMMARY_ONLY or base_skill in LOW_PRECISION_SUMMARY_ONLY)
                and effective_stype not in LOW_PRECISION_ALLOWED_SECTIONS
            ):
                token_log.append({
                    "raw_token": summary[start:end], "status": "filtered",
                    "reason": "low_precision: need req/preferred/responsibilities section",
                    "skill": skill, "section_type": stype,
                })
                continue
            if skill in ambiguous_for_summary and effective_stype not in AMBIGUOUS_ALLOWED_SECTIONS:
                continue
            if skill == "Diversity and Inclusion" and has_eeo:
                continue
            # context filters on summary matches (raw skill name; ±8 words)
            drop_reason = None
            for fn in context_filters:
                try:
                    reason = fn(
                        skill, matched, chunk, summary,
                        char_start=start - a, char_end=end - a,
                        company=company, job_title=job_title,
                    )
                except TypeError:
                    try:
                        reason = fn(
                            skill, matched, chunk, summary,
                            char_start=start - a, char_end=end - a,
                        )
                    except TypeError:
                        reason = fn(skill, matched, chunk, summary)
                if reason:
                    drop_reason = reason
                    break
            if drop_reason:
                token_log.append({
                    "raw_token": matched,
                    "status": "filtered",
                    "reason": drop_reason,
                    "skill": skill,
                    "section_type": stype,
                })
                continue
            key = (skill, start, end)
            if key in seen_spans:
                continue
            seen_spans.add(key)
            local_s, local_e = start - a, end - a
            _append_ev(
                skill=skill,
                source_field="summary",
                section_type=stype,
                matched_text=matched,
                char_start=start,
                char_end=end,
                evidence=centered_snippet(chunk, local_s, local_e),
                evidence_status="has_evidence",
                rule_id=f"{rule}:{skill}",
            )

    return rows, token_log


def aggregate_job_skills(evidence_df):
    """One row per (job_link, skill); merge sources; keep best evidence if any."""
    import pandas as pd

    cols = [
        "job_link", "skill", "sources", "n_evidence", "evidence_status",
        "matched_text", "evidence", "section_type", "rule_id",
        "char_start", "char_end",
    ]
    if evidence_df is None or len(evidence_df) == 0:
        return pd.DataFrame(columns=cols)

    records = []
    for (link, skill), g in evidence_df.groupby(["job_link", "skill"], sort=False):
        sources = sorted(set(g["source_field"].tolist()))
        has_ev = g["evidence_status"].eq("has_evidence")
        status = "has_evidence" if bool(has_ev.any()) else "ner_only"
        row = g.loc[has_ev].iloc[0] if has_ev.any() else g.iloc[0]
        records.append({
            "job_link": link,
            "skill": skill,
            "sources": "|".join(sources),
            "n_evidence": int(len(g)),
            "evidence_status": status,
            "matched_text": row["matched_text"],
            "evidence": row["evidence"] if status == "has_evidence" else None,
            "section_type": row["section_type"],
            "rule_id": row["rule_id"],
            "char_start": row["char_start"],
            "char_end": row["char_end"],
        })
    return pd.DataFrame.from_records(records, columns=cols)


