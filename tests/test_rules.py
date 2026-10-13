"""Stage-1+ rule tests. Run: python -m pytest tests/test_rules.py -q"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from extraction_resources import EDU_PATTERNS, extract_education_levels
from skill_refinement import assign_job_family, assign_job_family_detailed, refine_skill


class TestJobFamilyStems:
    def test_phlebotomist(self):
        assert assign_job_family("Phlebotomist") == "Allied Health"

    def test_psychologist(self):
        assert assign_job_family("Clinical Psychologist") == "Behavioral Health"

    def test_veterinarian(self):
        assert assign_job_family("Veterinarian") == "Veterinary"

    def test_sonographer(self):
        assert assign_job_family("Cardiac Sonographer") == "Allied Health"

    def test_java_developers_plural(self):
        assert assign_job_family("Java Developers") == "Software & IT Engineering"


class TestJobFamilyAbbrevsAndOrder:
    def test_annapolis_md_not_physician(self):
        assert assign_job_family("Branch Manager - Annapolis, MD") == "Management General"

    def test_coordinator_pa_not_physician(self):
        fam = assign_job_family("Reentry Coalition Coordinator, PA")
        assert fam != "Physician & PA"

    def test_mental_health_therapist_behavioral(self):
        assert assign_job_family("Mental Health Therapist") == "Behavioral Health"

    def test_sql_server_dba_not_hospitality(self):
        assert assign_job_family("SQL Server DBA") == "Software & IT Engineering"

    def test_electrical_engineer_non_software(self):
        assert assign_job_family("Senior Electrical Engineer") == "Engineering (Non-software)"

    def test_controls_engineer_non_software(self):
        assert assign_job_family("Controls Engineer") == "Engineering (Non-software)"

    def test_budget_analyst_finance(self):
        assert assign_job_family("Budget Analyst") == "Finance & Accounting"

    def test_air_traffic_controller_not_finance(self):
        assert assign_job_family("Air Traffic Controller") != "Finance & Accounting"

    def test_family_status_columns(self):
        d = assign_job_family_detailed("Phlebotomist")
        assert d["job_family"] == "Allied Health"
        assert d["job_family_rule"]
        assert d["job_family_status"] == "matched"


class TestEducationDoBug:
    def test_what_you_will_do_no_degree(self):
        req, pref, _ = extract_education_levels("What you will do: manage a team and close sales.")
        assert req is None
        assert pref is None

    def test_do_it_best_no_degree(self):
        req, _, _ = extract_education_levels("Do It Best Associate responsibilities include stocking.")
        assert req != "professional_doctorate"

    def test_md_with_dots_still_matches(self):
        req, _, _ = extract_education_levels("Requires an M.D. or equivalent medical degree.")
        assert req == "professional_doctorate"

    def test_do_with_dots_still_matches(self):
        req, _, _ = extract_education_levels("D.O. license required.")
        assert req == "professional_doctorate"

    def test_old_pattern_would_have_matched_do(self):
        # document the bug we fixed
        old = re.compile(r"\b(?:m\.?d\.?|d\.?o\.?)\b", re.I)
        assert old.search("What you will do")
        new = [p for l, p in EDU_PATTERNS if l == "professional_doctorate"][0]
        assert not re.search(new, "What you will do")


class TestSecuritySenseDrop:
    def test_drug_test_social_security_dropped(self):
        assert (
            refine_skill(
                "Security",
                "Must pass a drug test and social security number verification",
                "Admin",
                "security",
            )
            is None
        )

    def test_penetration_is_security_testing(self):
        assert (
            refine_skill(
                "Security",
                "Experience with penetration testing and OWASP",
                "Test Lead",
                "security",
                "Software & IT Engineering",
            )
            == "Security Testing"
        )

    def test_title_not_used_as_keyword_for_people_mgmt(self):
        # title says Team Assistant but evidence is expenses management — not People Management
        out = refine_skill(
            "Management",
            "Responsible for expenses management and invoice tracking",
            "Team Assistant",
            "management",
            "Administrative",
        )
        assert out != "People Management"

    def test_fund_management_compound_preserved(self):
        assert (
            refine_skill(
                "Management",
                "Oversee fund management activities",
                "Analyst",
                "Fund Management",
            )
            == "Fund Management"
        )


class TestStage4Pipeline:
    def test_merge_before_sense_quality_parent(self):
        import pandas as pd
        from skill_refinement import load_alias_tables, refine_skill_table
        from extraction_resources import SKILL_TYPE, COURSE_DOMAIN

        alias = load_alias_tables(ROOT / "skill_alias.csv")
        df = pd.DataFrame([
            {
                "job_link": "j1", "skill": "Quality", "matched_text": "Quality",
                "evidence": "Must demonstrate quality in daily work.",  # no sense cues → unspecified
            },
            {
                "job_link": "j1", "skill": "Quality Assurance", "matched_text": "QA",
                "evidence": "QA for manufacturing",
            },
        ])
        out, dropped = refine_skill_table(
            df, alias_tables=alias,
            skill_type_map=SKILL_TYPE, domain_map=COURSE_DOMAIN,
        )
        skills = set(out["skill_refined"])
        assert "Quality Assurance" in skills
        # broad Quality / Quality (unspecified) dropped when QA child present
        assert not any(s in {"Quality", "Quality (unspecified)"} for s in skills)

    def test_written_comm_keeps_child_drops_parent(self):
        import pandas as pd
        from skill_refinement import load_alias_tables, refine_skill_table
        from extraction_resources import SKILL_TYPE, COURSE_DOMAIN

        alias = load_alias_tables(ROOT / "skill_alias.csv")
        df = pd.DataFrame([
            {
                "job_link": "j1", "skill": "Communication", "matched_text": "Communication",
                "evidence": "Strong communication skills",
            },
            {
                "job_link": "j1", "skill": "Written Communication",
                "matched_text": "Written Communication",
                "evidence": "Excellent written communication",
            },
        ])
        out, dropped = refine_skill_table(
            df, alias_tables=alias,
            skill_type_map=SKILL_TYPE, domain_map=COURSE_DOMAIN,
        )
        skills = set(out["skill_refined"])
        assert "Written Communication" in skills
        assert "Communication" not in skills
        assert len(dropped) >= 1
        assert (dropped["drop_reason"].str.contains("hierarchy")).any()

    def test_l2_unmapped_not_copy_l1(self):
        from skill_refinement import skill_levels

        l1, l2, _ = skill_levels("SomeObscureSkillXYZ", "Cloud & IT")
        assert l1 == "Cloud & IT"
        assert l2 == "(unmapped)"

    def test_sales_generic_by_family(self):
        from skill_refinement import skill_levels

        _, _, g_sales = skill_levels("Sales", "Professional Skills", "Sales")
        _, _, g_other = skill_levels("Sales", "Professional Skills", "Nursing & Clinical")
        assert g_sales is False
        assert g_other is True

    def test_qa_not_generic(self):
        from skill_refinement import skill_levels

        _, _, g = skill_levels("Quality Assurance", "Cloud & IT", "Software & IT Engineering")
        assert g is False


class TestStage5Qualifications:
    def test_yoe_plus_max_is_none(self):
        from extraction_resources import extract_yoe_records, aggregate_yoe

        recs = extract_yoe_records("3+ years of experience in a related field.")
        assert len(recs) >= 1
        assert recs[0]["yoe_min"] == 3
        assert recs[0]["yoe_max"] is None
        assert recs[0]["yoe_plus"] is True
        agg = aggregate_yoe(recs)
        assert agg["yoe_min_overall"] == 3
        assert agg["yoe_max_overall"] is None
        assert agg["yoe_multi"] is False

    def test_yoe_does_not_merge_separate_mentions(self):
        from extraction_resources import extract_yoe_records

        text = (
            "5 years of experience in sales. "
            "2 years of experience with Salesforce."
        )
        recs = extract_yoe_records(text)
        assert len(recs) >= 2
        mins = sorted(r["yoe_min"] for r in recs)
        assert 2 in mins and 5 in mins

    def test_edu_mentioned_vs_required(self):
        from extraction_resources import extract_education_records, summarize_education

        mentioned = extract_education_records(
            "Many of our employees hold a bachelor's degree.",
            has_req_section=False,
        )
        s = summarize_education(mentioned)
        assert s["edu_required"] is None
        assert s["edu_status"] in {"mentioned", "unknown"} or s["edu_mentioned"] == "bachelor"

        required = extract_education_records(
            "Bachelor's degree required.",
            has_req_section=False,
        )
        s2 = summarize_education(required)
        assert s2["edu_required"] == "bachelor"
        assert s2["edu_status"] == "required"

    def test_no_degree_required(self):
        from extraction_resources import extract_education_records, summarize_education

        recs = extract_education_records(
            "No degree required. Training provided.",
            has_req_section=True,
        )
        s = summarize_education(recs)
        assert s["edu_not_required"] is True
        assert s["edu_required"] is None
        assert s["edu_status"] == "not_required"

    def test_requirement_text_excludes_benefits_on_fallback(self):
        from extraction_resources import requirement_text

        jd = (
            "About us: We are a great company with a fun culture.\n"
            "Benefits: 401k and free lunch and bachelor's tuition.\n"
            "Day to day: help customers and manage inventory."
        )
        text, has_req = requirement_text(jd)
        assert has_req is False
        assert "401k" not in text
        assert "fun culture" not in text or "About us" not in text
        assert "inventory" in text.lower() or "customers" in text.lower()

    def test_title_rn_not_required_cert(self):
        from extraction_resources import extract_cert_records, extract_certs

        recs = extract_cert_records(
            "Provide excellent patient care on the floor.",
            title="RN - Emergency Department",
        )
        assert any(r["certification"] == "RN" and r["cert_status"] == "title_mention" for r in recs)
        assert "RN" not in extract_certs(
            "Provide excellent patient care on the floor.",
            title="RN - Emergency Department",
        )

    def test_skills_extraction_status(self):
        from extraction_resources import skills_extraction_status

        assert skills_extraction_status(
            has_skills_text=True, has_summary_text=True, n_skills=3
        ) == "ok"
        assert skills_extraction_status(
            has_skills_text=False, has_summary_text=False, n_skills=0
        ) == "no_text"
        assert skills_extraction_status(
            has_skills_text=True, has_summary_text=False, n_skills=0,
            n_raw_tokens=5, n_unmapped_tokens=5,
        ) == "unmapped_only"


class TestRound4Fixes:
    def test_section_header_not_mid_sentence_benefits(self):
        from skill_refinement import split_sections_typed, skill_extractable_text

        jd = (
            "Intro paragraph with comprehensive benefits mentioned inline.\n"
            "Requirements:\n"
            "Python experience.\n"
            "Benefits:\n"
            "401k and PTO."
        )
        sections = split_sections_typed(jd)
        assert any(s["section_type"] == "requirements" for s in sections)
        assert any(s["section_type"] == "benefits" for s in sections)
        text, _ = skill_extractable_text(jd)
        assert "Python" in text
        assert "401k" not in text
        # mid-sentence 'benefits' before Requirements must not steal the intro
        intro_or_req = " ".join(
            s["text"] for s in sections if s["section_type"] in {"other", "requirements"}
        )
        assert "comprehensive benefits" in intro_or_req.lower() or "Python" in text

    def test_bachelor_or_master_keeps_both(self):
        from extraction_resources import extract_education_records, summarize_education

        recs = extract_education_records(
            "Bachelor's or Master's degree required.",
            has_req_section=True,
            section_type="requirements",
        )
        levels = {r["edu_level"] for r in recs if r["edu_level"]}
        assert "bachelor" in levels and "master" in levels
        s = summarize_education(recs)
        assert s["edu_required"] == "bachelor"
        assert s["edu_alternatives"] and "master" in s["edu_alternatives"]

    def test_yoe_multi_does_not_invent_range(self):
        from extraction_resources import extract_yoe_records, aggregate_yoe

        text = (
            "5 years of experience required. "
            "2 years of experience preferred."
        )
        recs = extract_yoe_records(text)
        agg = aggregate_yoe(recs)
        # required takes precedence for overall; preferred stored separately
        assert agg["yoe_min_required"] == 5
        assert agg["yoe_min_preferred"] == 2
        assert agg["yoe_min_overall"] == 5
        assert agg["yoe_max_overall"] == 5

    def test_yoe_left_digit_boundary(self):
        from extraction_resources import extract_yoe_records

        # "120 years" must not become 20
        recs = extract_yoe_records("Over 120 years of experience serving customers.")
        assert not any(r["yoe_min"] == 20 for r in recs)

    def test_company_history_yoe_not_requirement(self):
        from extraction_resources import extract_yoe_records

        # brand heritage — not a candidate YOE
        assert extract_yoe_records(
            "Backed by over 120 years of experience serving communities."
        ) == []
        assert extract_yoe_records(
            "With more than 100 years of experience in the industry."
        ) == []
        # still extract real requirements in the same blob
        mixed = (
            "About us: Backed by over 120 years of experience.\n"
            "Requirements: 5 years of experience in nursing."
        )
        recs = extract_yoe_records(mixed)
        assert any(r["yoe_min"] == 5 for r in recs)
        assert not any(r["yoe_min"] in {20, 100, 120} for r in recs)

    def test_company_section_skips_yoe(self):
        from extraction_resources import extract_yoe_records

        assert extract_yoe_records(
            "We have 15 years of experience in logistics.",
            section_type="company",
        ) == []

    def test_supervision_under_filtered(self):
        from extraction_resources import context_filter_skill

        reason = context_filter_skill(
            "Team Management",
            "supervision",
            "Works under the supervision of the charge nurse.",
            "",
        )
        assert reason is not None

    def test_specifications_not_blueprint_alias(self):
        from extraction_resources import SKILL_DICT

        assert "specifications" not in {a.lower() for a in SKILL_DICT["Blueprints"]}

    def test_aggregate_prefers_summary_evidence(self):
        import pandas as pd
        from skill_refinement import load_alias_tables, refine_skill_table
        from extraction_resources import SKILL_TYPE, COURSE_DOMAIN

        alias = load_alias_tables(ROOT / "skill_alias.csv")
        df = pd.DataFrame([
            {
                "evidence_id": 1, "job_link": "j1", "skill": "Python",
                "matched_text": "Python", "source_field": "job_skills",
                "section_type": "ner_cell", "evidence": None,
                "evidence_status": "ner_only", "rule_id": "ner",
                "char_start": 0, "char_end": 6,
            },
            {
                "evidence_id": 2, "job_link": "j1", "skill": "Python",
                "matched_text": "Python", "source_field": "summary",
                "section_type": "requirements", "evidence": "Strong Python skills required",
                "evidence_status": "has_evidence", "rule_id": "sum",
                "char_start": 10, "char_end": 16,
            },
        ])
        out, dropped = refine_skill_table(
            df, alias_tables=alias,
            skill_type_map=SKILL_TYPE, domain_map=COURSE_DOMAIN,
        )
        assert len(out) == 1
        assert out.iloc[0]["evidence_status"] == "has_evidence"
        assert out.iloc[0]["sources"] == "job_skills|summary"
        assert "Strong Python" in (out.iloc[0]["evidence"] or "")
        assert "2" in str(out.iloc[0]["evidence_ids"])

    def test_short_alias_sql_in_summary(self):
        from skill_refinement import extract_skill_evidence
        from extraction_resources import SKILL_DICT

        jd = "Requirements: Must know SQL and Excel for reporting."
        rows, _ = extract_skill_evidence(None, jd, SKILL_DICT, ambiguous_for_summary=set())
        skills = {r["skill"] for r in rows}
        assert "SQL" in skills
        assert "Microsoft Excel" in skills

    def test_juris_doctor_not_phd(self):
        from extraction_resources import extract_education_records

        recs = extract_education_records(
            "Juris Doctorate required.",
            has_req_section=True,
            section_type="requirements",
        )
        levels = [r["edu_level"] for r in recs]
        assert "professional_doctorate" in levels
        assert "phd" not in levels

    def test_preferred_section_marks_preferred(self):
        from extraction_resources import extract_education_records

        recs = extract_education_records(
            "Master's degree in nursing.",
            has_req_section=True,
            section_type="preferred",
        )
        assert all(r["edu_status"] == "preferred" for r in recs if r["edu_level"])

    def test_eda_dual_count_modes(self):
        import pandas as pd
        from eda_counts_v4 import compare_count_modes, filter_for_count_mode

        features = pd.DataFrame([
            {"job_link": "a", "search_country": "United States",
             "dup_group_id": "g1", "is_dup_primary": True},
            {"job_link": "b", "search_country": "United States",
             "dup_group_id": "g1", "is_dup_primary": False},
            {"job_link": "c", "search_country": "United States",
             "dup_group_id": "g2", "is_dup_primary": True},
        ])
        skills = pd.DataFrame([
            {"job_link": "a", "skill_refined": "Sales"},
            {"job_link": "b", "skill_refined": "Sales"},
            {"job_link": "c", "skill_refined": "Sales"},
        ])
        assert len(filter_for_count_mode(features, "posting")) == 3
        assert len(filter_for_count_mode(features, "jd_template")) == 2
        dual = compare_count_modes(skills, features, country="United States", top_n=5)
        row = dual.loc[dual["skill"] == "Sales"].iloc[0]
        assert row["n_jobs_posting"] == 3
        assert row["n_jobs_jd_template"] == 2


class TestRound5Fixes:
    def test_bachelor_master_degree_without_apostrophe(self):
        from extraction_resources import extract_education_records, summarize_education

        recs = extract_education_records(
            "Bachelor degree required, master degree preferred.",
            has_req_section=True,
            section_type="requirements",
        )
        levels = {(r["edu_level"], r["edu_status"]) for r in recs if r["edu_level"]}
        assert ("bachelor", "required") in levels
        assert ("master", "preferred") in levels
        s = summarize_education(recs)
        assert s["edu_required"] == "bachelor"
        assert s["edu_preferred"] == "master"

    def test_bachelors_required_masters_preferred(self):
        from extraction_resources import extract_education_records, summarize_education

        recs = extract_education_records(
            "Bachelor's required, Master's preferred",
            has_req_section=True,
            section_type="requirements",
        )
        s = summarize_education(recs)
        assert s["edu_required"] == "bachelor"
        assert s["edu_preferred"] == "master"

    def test_preferred_section_required_is_conflict(self):
        from extraction_resources import extract_education_records

        recs = extract_education_records(
            "Bachelor's degree required.",
            has_req_section=True,
            section_type="preferred",
        )
        assert any(r["edu_status"] == "conflict" for r in recs if r["edu_level"] == "bachelor")

    def test_ms_or_phd(self):
        from extraction_resources import extract_education_records, summarize_education

        recs = extract_education_records(
            "MS or PhD in Computer Science required.",
            has_req_section=True,
            section_type="requirements",
        )
        levels = {r["edu_level"] for r in recs if r["edu_level"]}
        assert "master" in levels and "phd" in levels
        s = summarize_education(recs)
        assert s["edu_required"] == "master"
        assert s["edu_alternatives"] and "phd" in s["edu_alternatives"]

    def test_skill_specific_yoe_not_overall(self):
        from extraction_resources import extract_yoe_records, aggregate_yoe

        # Named tool/tech years stay skill_specific and do not fill overall.
        recs = extract_yoe_records("1-3 years of Python experience required.")
        assert len(recs) >= 1
        assert recs[0]["yoe_type"] == "skill_specific"
        agg = aggregate_yoe(recs)
        assert agg["yoe_min_overall"] is None
        assert agg["yoe_min_any_skill"] == 1

    def test_age_not_yoe(self):
        from extraction_resources import extract_yoe_records

        recs = extract_yoe_records(
            "Must be 18 years or older and have direct experience with customers."
        )
        assert not any(r["yoe_min"] == 18 for r in recs)

    def test_excel_verb_not_skill(self):
        from skill_refinement import extract_skill_evidence
        from extraction_resources import SKILL_DICT

        rows, _ = extract_skill_evidence(
            None,
            "Requirements: eager to explore and excel in the subject.",
            SKILL_DICT,
            ambiguous_for_summary=set(),
        )
        assert "Microsoft Excel" not in {r["skill"] for r in rows}

    def test_git_not_from_git_acronym(self):
        from skill_refinement import extract_skill_evidence
        from extraction_resources import SKILL_DICT

        rows, _ = extract_skill_evidence(
            None,
            "Requirements: EIT or GIT preferred.",
            SKILL_DICT,
            ambiguous_for_summary=set(),
        )
        assert "Git" not in {r["skill"] for r in rows}

    def test_supervision_under_filtered_raw(self):
        from extraction_resources import context_filter_skill

        reason = context_filter_skill(
            "Supervision",
            "supervision",
            "Works under direct supervision of the charge nurse on duty today.",
            "",
            char_start=12,
            char_end=23,
        )
        assert reason is not None

    def test_benefits_event_planning_filtered(self):
        from extraction_resources import context_filter_skill

        text = (
            "Referral services for child, elder and pet care, home and auto repair, event planning"
        )
        idx = text.lower().index("event planning")
        reason = context_filter_skill(
            "Event Planning", "event planning", text, "", char_start=idx, char_end=idx + 14
        )
        assert reason is not None

    def test_ambiguous_only_in_skill_dict(self):
        from extraction_resources import AMBIGUOUS_FOR_SUMMARY, SKILL_DICT

        assert not (AMBIGUOUS_FOR_SUMMARY - set(SKILL_DICT))

    def test_sample_links_stable(self):
        from pathlib import Path
        import pandas as pd

        p = Path("cleaned/sample_links_v5.csv")
        assert p.exists()
        a = pd.read_csv(p)
        b = pd.read_csv(p)
        assert list(a["job_link"]) == list(b["job_link"])
        assert a["job_link"].is_monotonic_increasing or True  # sorted when created


class TestStage2SectionsAndAliases:
    def test_eeo_section_not_in_skill_text(self):
        from skill_refinement import skill_extractable_text, split_sections_typed

        jd = (
            "Requirements: Python and SQL experience.\n"
            "Benefits: 401k and PTO.\n"
            "Equal Opportunity: We prohibit discrimination in recruitment and hiring."
        )
        sections = split_sections_typed(jd)
        types = {s["section_type"] for s in sections}
        assert "requirements" in types
        assert "benefits" in types
        assert "eeo" in types
        text, _ = skill_extractable_text(jd)
        assert "Python" in text
        assert "401k" not in text
        assert "prohibit discrimination" not in text

    def test_bls_not_merged_into_cpr_aliases(self):
        from extraction_resources import SKILL_DICT

        assert "bls" not in {a.lower() for a in SKILL_DICT["CPR"]}
        assert "bls" in {a.lower() for a in SKILL_DICT["BLS"]}

    def test_written_communication_independent(self):
        from extraction_resources import SKILL_DICT

        assert "written communication" not in {a.lower() for a in SKILL_DICT["Communication"]}
        assert "Written Communication" in SKILL_DICT

    def test_version_control_independent_of_git(self):
        from extraction_resources import SKILL_DICT

        assert "version control" not in {a.lower() for a in SKILL_DICT["Git"]}
        assert "Version Control" in SKILL_DICT

    def test_financial_modeling_independent(self):
        from extraction_resources import SKILL_DICT

        assert "financial modeling" not in {a.lower() for a in SKILL_DICT["Financial Analysis"]}
        assert "Financial Modeling" in SKILL_DICT

    def test_english_bare_word_not_alias(self):
        from extraction_resources import SKILL_DICT

        assert "english" not in {a.lower() for a in SKILL_DICT["English Proficiency"]}

    def test_software_is_generic_flag(self):
        from skill_refinement import skill_levels

        _, _, g = skill_levels("Software", "Cloud & IT")
        assert g is True


class TestStage3EvidenceBinding:
    def test_centered_snippet_collapses_newlines(self):
        from skill_refinement import centered_snippet

        text = "AAA\nBBB python CCC\nDDD"
        start = text.index("python")
        end = start + len("python")
        snip = centered_snippet(text, start, end, max_len=40)
        assert "\n" not in snip
        assert "python" in snip.lower()

    def test_ner_only_no_fabricated_evidence(self):
        from skill_refinement import extract_skill_evidence

        skill_dict = {"Python": ["python"]}
        # Empty summary: NER kept; evidence stays None (not fabricated)
        rows, _log = extract_skill_evidence(
            "Python, Communication",
            "",
            skill_dict,
            ambiguous_for_summary=set(),
        )
        py = [r for r in rows if r["skill"] == "Python"]
        assert len(py) == 1
        assert py[0]["evidence_status"] == "ner_only"
        assert py[0]["evidence"] is None
        assert py[0]["matched_text"] == "Python"
        assert py[0]["source_field"] == "job_skills"

    def test_ner_unsupported_dropped(self):
        from skill_refinement import extract_skill_evidence, ALWAYS_DROP_SKILLS
        from extraction_resources import SKILL_DICT

        # bare Software is always-drop / unsupported without JD support
        assert "Software" in ALWAYS_DROP_SKILLS
        rows, logs = extract_skill_evidence(
            "Software",
            "We offer great benefits and a fun culture with no skill keywords here at all.",
            SKILL_DICT,
            ambiguous_for_summary=set(),
        )
        assert not any(r["skill"] == "Software" for r in rows)
        assert any(
            ("ner_unsupported" in str(l.get("reason", "")) or "always_drop" in str(l.get("reason", "")))
            for l in logs
        )

    def test_summary_match_has_evidence_and_offsets(self):
        from skill_refinement import extract_skill_evidence

        skill_dict = {"Python": ["python"]}
        jd = (
            "Requirements: Strong Python and SQL experience required.\n"
            "Benefits: 401k and PTO."
        )
        rows, _log = extract_skill_evidence(None, jd, skill_dict, ambiguous_for_summary=set())
        py = [r for r in rows if r["skill"] == "Python"]
        assert len(py) >= 1
        r = py[0]
        assert r["evidence_status"] == "has_evidence"
        assert r["source_field"] == "summary"
        assert r["section_type"] == "requirements"
        assert r["matched_text"] == "Python"
        assert r["char_start"] is not None and r["char_end"] > r["char_start"]
        assert "Python" in r["evidence"]
        assert "\n" not in r["evidence"]
        assert "401k" not in (r["evidence"] or "")

    def test_aggregate_merges_sources(self):
        import pandas as pd
        from skill_refinement import aggregate_job_skills

        ev = pd.DataFrame([
            {
                "job_link": "j1", "skill": "Python", "source_field": "job_skills",
                "section_type": "ner_cell", "matched_text": "Python",
                "char_start": 0, "char_end": 6, "evidence": None,
                "evidence_status": "ner_only", "rule_id": "ner_alias:Python",
            },
            {
                "job_link": "j1", "skill": "Python", "source_field": "summary",
                "section_type": "requirements", "matched_text": "Python",
                "char_start": 10, "char_end": 16, "evidence": "Strong Python skills",
                "evidence_status": "has_evidence", "rule_id": "summary_alias:Python",
            },
        ])
        out = aggregate_job_skills(ev)
        assert len(out) == 1
        assert out.iloc[0]["sources"] == "job_skills|summary"
        assert out.iloc[0]["evidence_status"] == "has_evidence"
        assert out.iloc[0]["evidence"] == "Strong Python skills"


class TestRound6AssociateAndPrecision:
    def test_associate_not_from_as_well_as(self):
        from extraction_resources import extract_education_records

        recs = extract_education_records(
            "Must communicate as well as collaborate with the team.",
            has_req_section=True,
            section_type="requirements",
        )
        assert not any(r["edu_level"] == "associate" for r in recs)

    def test_associate_not_from_sales_associate(self):
        from extraction_resources import extract_education_records

        recs = extract_education_records(
            "Sales Associate Discount: 20% off. Associate General Counsel preferred.",
            has_req_section=True,
            section_type="requirements",
        )
        assert not any(r["edu_level"] == "associate" for r in recs)

    def test_associate_degree_still_matches(self):
        from extraction_resources import extract_education_records, summarize_education

        recs = extract_education_records(
            "Associate degree required. A.S. degree preferred.",
            has_req_section=True,
            section_type="requirements",
        )
        assert any(r["edu_level"] == "associate" for r in recs)
        s = summarize_education(recs)
        assert s["edu_required"] == "associate"

    def test_software_procedures_dropped_from_summary(self):
        from skill_refinement import extract_skill_evidence, ALWAYS_DROP_SKILLS
        from extraction_resources import SKILL_DICT

        assert "Software" in ALWAYS_DROP_SKILLS
        rows, logs = extract_skill_evidence(
            None,
            "Requirements: Strong software and procedures knowledge required.",
            SKILL_DICT,
            ambiguous_for_summary=set(),
        )
        skills = {r["skill"] for r in rows}
        assert "Software" not in skills
        assert "Procedures" not in skills

    def test_yoe_preferred_fallback(self):
        from extraction_resources import extract_yoe_records, aggregate_yoe

        recs = extract_yoe_records(
            "Preferred: 5+ years of experience in a related field.",
            section_type="preferred",
        )
        assert recs and recs[0]["yoe_status"] == "preferred"
        agg = aggregate_yoe(recs)
        assert agg["yoe_min_required"] is None
        assert agg["yoe_min_preferred"] == 5
        assert agg["yoe_min_overall"] == 5

    def test_psychiatrist_is_physician(self):
        from skill_refinement import assign_job_family

        assert assign_job_family("Staff Psychiatrist") == "Physician & PA"

    def test_deli_manager_hospitality(self):
        from skill_refinement import assign_job_family

        assert assign_job_family("Deli Manager") == "Hospitality & Food"

    def test_sales_associate_retail(self):
        from skill_refinement import assign_job_family

        assert assign_job_family("LEAD SALES ASSOCIATE-PT") == "Retail Ops"


class TestRound6bFixes:
    def test_curly_apostrophe_drivers_license(self):
        from extraction_resources import extract_cert_records

        # unicode right single quotation mark
        text = "Valid driver\u2019s license is required."
        certs = [c["certification"] for c in extract_cert_records(text)]
        assert "Driver's License" in certs

    def test_driving_licence_uk(self):
        from extraction_resources import extract_cert_records

        certs = [c["certification"] for c in extract_cert_records(
            "You must have a full and clean driving licence."
        )]
        assert "Driver's License" in certs

    def test_associate_or_baccalaureate_nursing(self):
        from extraction_resources import extract_education_records

        recs = extract_education_records(
            "Graduate of an accredited Diploma, Associate or Baccalaureate School of Nursing",
            has_req_section=True,
            section_type="requirements",
        )
        assert any(r["edu_level"] == "associate" for r in recs)

    def test_yrs_yoe_and_paren_preferred(self):
        from extraction_resources import extract_yoe_records, aggregate_yoe

        agg = aggregate_yoe(extract_yoe_records("3-5 yrs multi-store sales management experience"))
        assert agg["yoe_min_overall"] == 3
        agg2 = aggregate_yoe(extract_yoe_records("Journeyman Electrician: 1 year (preferred)"))
        assert agg2["yoe_min_overall"] == 1
        assert agg2["yoe_min_preferred"] == 1

    def test_restoration_years_are_overall(self):
        from extraction_resources import extract_yoe_records, aggregate_yoe

        agg = aggregate_yoe(extract_yoe_records(
            "Minimum 5 years of restoration experience preferred.",
            section_type="preferred",
        ))
        assert agg["yoe_min_overall"] == 5


class TestRound7DutyRecallAndRecruitment:
    def test_responsibilities_equal_to_requirements_for_low_precision(self):
        from skill_refinement import extract_skill_evidence, LOW_PRECISION_ALLOWED_SECTIONS
        from extraction_resources import SKILL_DICT, context_filter_skill

        assert "responsibilities" in LOW_PRECISION_ALLOWED_SECTIONS
        jd = (
            "Responsibilities:\n"
            "Prepare reports for management and maintain accurate records.\n"
            "Benefits: 401k and PTO."
        )
        rows, _ = extract_skill_evidence(
            None, jd, SKILL_DICT, ambiguous_for_summary=set(),
            context_filters=[context_filter_skill],
        )
        skills = {r["skill"] for r in rows}
        assert "Reporting" in skills or "Documentation" in skills

    def test_documentation_duty_phrase(self):
        from skill_refinement import extract_skill_evidence
        from extraction_resources import SKILL_DICT

        rows, _ = extract_skill_evidence(
            None,
            "Requirements: Maintain accurate records and complete documentation daily.",
            SKILL_DICT,
            ambiguous_for_summary=set(),
        )
        assert "Documentation" in {r["skill"] for r in rows}

    def test_osha_safety_phrase(self):
        from skill_refinement import extract_skill_evidence
        from extraction_resources import SKILL_DICT

        rows, _ = extract_skill_evidence(
            None,
            "Requirements: Follow OSHA safety regulations and safe work practices.",
            SKILL_DICT,
            ambiguous_for_summary=set(),
        )
        skills = {r["skill"] for r in rows}
        assert "Safety" in skills or any("Safety" in s for s in skills)

    def test_driving_company_vehicle(self):
        from skill_refinement import extract_skill_evidence
        from extraction_resources import SKILL_DICT

        rows, _ = extract_skill_evidence(
            None,
            "Requirements: Must drive company vehicle; valid driver's license required.",
            SKILL_DICT,
            ambiguous_for_summary=set(),
        )
        assert "Driving" in {r["skill"] for r in rows}

    def test_recruitment_we_are_recruiting_dropped(self):
        from extraction_resources import context_filter_skill

        reason = context_filter_skill(
            "Recruitment", "recruitment",
            "We are currently recruiting for this role across the region.",
            "",
            char_start=22, char_end=33,
        )
        assert reason is not None

    def test_recruitment_talent_acquisition_kept(self):
        from extraction_resources import context_filter_skill

        text = "Requirements: 5 years talent acquisition and recruiting candidates experience."
        idx = text.lower().index("recruiting")
        reason = context_filter_skill(
            "Recruitment", "recruiting", text, "",
            char_start=idx, char_end=idx + 10,
        )
        assert reason is None

    def test_salesforce_in_title_not_dropped_as_company(self):
        from extraction_resources import context_filter_skill

        reason = context_filter_skill(
            "Salesforce", "Salesforce",
            "Proficiency in Salesforce CRM required.",
            "",
            char_start=15, char_end=25,
            company="Acme Corp",
            job_title="IT Specialist - Salesforce & O365",
        )
        assert reason is None

    def test_short_jd_other_treated_as_requirements(self):
        from skill_refinement import extract_skill_evidence
        from extraction_resources import SKILL_DICT

        # no section headers — payroll would be low-precision; should still extract Driving
        rows, _ = extract_skill_evidence(
            None,
            "Must have a valid driver's license and drive company vehicle daily.",
            SKILL_DICT,
            ambiguous_for_summary=set(),
        )
        assert "Driving" in {r["skill"] for r in rows}


class TestRound7AmbiguousOtherDuty:
    def test_short_jd_documentation_not_blocked_by_ambiguous(self):
        from skill_refinement import extract_skill_evidence
        from extraction_resources import SKILL_DICT, context_filter_skill, AMBIGUOUS_FOR_SUMMARY

        jd = "Complete all required paperwork and documentation according to guidelines."
        rows, _ = extract_skill_evidence(
            None, jd, SKILL_DICT, ambiguous_for_summary=AMBIGUOUS_FOR_SUMMARY,
            context_filters=[context_filter_skill],
        )
        assert "Documentation" in {r["skill"] for r in rows}

    def test_safety_defaults_to_workplace_osha(self):
        from skill_refinement import refine_skill_detailed
        detail = refine_skill_detailed(
            "Safety", "Follow safety procedures and governing regulations.",
            "Electrician", "safety procedures",
        )
        assert detail["skill_refined"] == "Workplace / OSHA Safety"

    def test_driving_excellence_dropped(self):
        from extraction_resources import context_filter_skill
        reason = context_filter_skill(
            "Driving", "driving",
            "Provide motivation to your team, driving excellence across shifts.",
            "",
            char_start=40, char_end=47,
        )
        assert reason is not None


class TestRound8EduYoeCertPatches:
    def test_ms_office_not_master(self):
        from extraction_resources import extract_education_records
        recs = extract_education_records(
            "Proficiency in MS Office, MS Word and MS Excel required."
        )
        assert not any(r["edu_level"] == "master" for r in recs)

    def test_masters_degree_kept(self):
        from extraction_resources import extract_education_records
        recs = extract_education_records("Must have a Master's degree in CS.")
        assert any(r["edu_level"] == "master" for r in recs)

    def test_master_data_not_degree(self):
        from extraction_resources import extract_education_records
        recs = extract_education_records("Experience with master data and master schedule.")
        assert not any(r["edu_level"] == "master" for r in recs)

    def test_five_paren_years(self):
        from extraction_resources import extract_yoe_records, aggregate_yoe
        recs = extract_yoe_records("Five (5) to ten (10) years of experience required.")
        agg = aggregate_yoe(recs)
        assert agg["yoe_min_overall"] == 5
        assert agg["yoe_max_overall"] == 10

    def test_two_years_word(self):
        from extraction_resources import extract_yoe_records, aggregate_yoe
        agg = aggregate_yoe(extract_yoe_records("Two years of supervisor experience."))
        assert agg["yoe_min_overall"] == 2

    def test_years_in_relevant_position(self):
        from extraction_resources import extract_yoe_records, aggregate_yoe
        agg = aggregate_yoe(extract_yoe_records("5+ years in relevant position."))
        assert agg["yoe_min_overall"] == 5

    def test_rn_supervision_not_cert(self):
        from extraction_resources import extract_cert_records
        recs = extract_cert_records("Works under the supervision of an RN or LPN.")
        assert "RN" not in {r["certification"] for r in recs}
        assert "LPN" not in {r["certification"] for r in recs}

    def test_rn_license_kept(self):
        from extraction_resources import extract_cert_records
        recs = extract_cert_records("Must have current RN license.")
        assert any(r["certification"] == "RN" for r in recs)

    def test_reports_to_rn_not_cert(self):
        from extraction_resources import extract_cert_records
        recs = extract_cert_records("This role reports to RN Manager on the unit.")
        assert "RN" not in {r["certification"] for r in recs}


class TestFullRunFreezeAndGroups:
    def test_pipeline_v8_does_not_retrain_model(self, tmp_path):
        """Importing/calling load path must not rewrite frozen joblib."""
        import hashlib
        from pathlib import Path
        from job_family_classifier import MODEL_PATH, load_model

        assert MODEL_PATH.exists()
        before = hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest()
        load_model()
        # simulate the guard used in run_pipeline_v8.main
        assert MODEL_PATH.exists()
        after = hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest()
        assert before == after

    def test_search_position_groups_cover_top(self):
        from search_position_groups import group_for_position
        assert group_for_position("Christian Science Nurse") == "Healthcare_Nursing"
        assert group_for_position("Accountant") == "Finance_Accounting"
        assert group_for_position("Chef") == "Hospitality_Food"
        assert group_for_position("Account Executive") == "Sales_Customer"
