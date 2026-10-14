"""Tests for the analysis layer (summaries, models, dashboard) on a tiny synthetic dataset."""

import argparse
import json

import numpy as np
import pandas as pd
import pytest

from src.analysis import build_summaries, config, models

GROUPS = {"Tech_Engineering": ["Python", "SQL", "AWS", "Git"],
          "Healthcare_Nursing": ["Nursing", "Patient Care", "CPR", "Care Planning"],
          "Finance_Accounting": ["Accounting", "Auditing", "GAAP", "Budgeting"]}


@pytest.fixture(scope="module")
def data(tmp_path_factory):
    d = tmp_path_factory.mktemp("in")
    rng = np.random.default_rng(0)
    jobs, skills, certs = [], [], []
    for i in range(600):
        grp = list(GROUPS)[i % 3]
        link = f"https://x/{i}"
        # jobs 0 and 1 of every 100 share a dup group -> one of them is dropped
        dup = f"g{i - 1}" if i % 100 == 1 else f"g{i}"
        jobs.append(dict(job_link=link, job_title="t", company="c", search_country=["United States", "Canada"][i % 2],
                         search_position="p", position_group=grp, job_level="Mid Senior", job_type="Onsite",
                         dup_group_id=dup, is_dup_primary=i % 100 != 1, text_status="ok",
                         edu_required="bachelor" if i % 4 == 0 else None, edu_preferred=None,
                         yoe_min_overall=3.0 if i % 5 == 0 else None, yoe_min_preferred=None, job_family_pred="x"))
        own = list(rng.choice(GROUPS[grp], 3, replace=False))
        for s in own + ["Communication"]:
            skills.append(dict(job_link=link, skill=s, sources="summary", evidence_status="has_evidence",
                               is_generic=False, high_confidence=s == own[0]))
        skills.append(dict(job_link=link, skill="Management (unspecified)", sources="summary",
                           evidence_status="has_evidence", is_generic=True, high_confidence=False))
        if grp == "Healthcare_Nursing":
            certs.append(dict(job_link=link, cert="RN", cert_status="required"))
    paths = {}
    for name, rows in (("jobs", jobs), ("skills", skills), ("certs", certs)):
        paths[name] = [d / f"{name}.parquet"]
        pd.DataFrame(rows).to_parquet(paths[name][0], index=False)
    paths["summary_dir"] = tmp_path_factory.mktemp("summary")
    return paths


def test_parse_chunks():
    assert config.parse_chunks("0-2,5") == [0, 1, 2, 5]
    assert [p.name for p in config.chunk_paths("jobs", "1")] == ["jobs_chunk_0001.parquet"]


def test_resolve_inputs_missing(tmp_path):
    ns = argparse.Namespace(preset="full", chunks="0", chunk_dir=tmp_path, jobs=[tmp_path / "nope.parquet"],
                            skills=None, certs=None, summary_dir=None)
    with pytest.raises(SystemExit):
        config.resolve_inputs(ns)


def test_build_summaries(data):
    ov = build_summaries.build(data, top_n=20)
    out = data["summary_dir"]
    assert ov["n_postings_raw"] == 600 and ov["n_postings_dedup"] == 594  # dedup by dup_group_id
    freq = pd.read_csv(out / "skill_freq_overall.csv")
    assert not freq.skill.str.contains("unspecified").any()  # generic labels excluded by default
    assert "Management (unspecified)" in set(pd.read_csv(out / "skill_freq_overall_incl_generic.csv").skill)
    top = freq.iloc[0]
    assert top.skill == "Communication" and top.share_jobs == pytest.approx(1.0)
    assert (freq.n_jobs_hc <= freq.n_jobs).all() and freq.n_jobs_hc.sum() == 594
    by = pd.read_csv(out / "skill_freq_by_position_group.csv")
    py = by[(by.skill == "Python")]
    assert set(py.position_group) == {"Tech_Engineering"} and py.lift_vs_overall.iloc[0] > 2.5
    co = pd.read_csv(out / "skill_cooccurrence_top20.csv")
    a = co[(co.skill_a == "Nursing") & (co.skill_b == "Patient Care")].iloc[0]
    assert a.lift > 1 and a.n_co <= min(a.n_a, a.n_b)
    assert not ((co.skill_a == "Accounting") & (co.skill_b == "Python")).any()
    cert = pd.read_csv(out / "cert_occurrence.csv")
    assert cert.cert[0] == "RN" and cert.share_jobs[0] == pytest.approx(198 / 594, abs=0.01)
    edu = pd.read_csv(out / "edu_dist.csv")
    assert edu.n_jobs.sum() == 594 and set(edu.edu_required) == {"bachelor", "not_stated"}
    cube, jobs = pd.read_csv(out / "skill_freq_cube.csv"), pd.read_csv(out / "jobs_cube.csv")
    assert jobs.n_jobs.sum() == 594
    assert cube[cube.skill == "Communication"].n_jobs.sum() == 594
    assert json.loads((out / "overview.json").read_text())["quality"]["skill_precision"] == 0.66


def test_models(data):
    X, jobs, skills, _ = models.load_matrix(data, min_skills=3, min_skill_jobs=5)
    assert X.shape == (594, 13) and X.max() == 1
    prof = models.run_profiles(X, jobs, skills, k_grid=[2, 3], top_n=5, sil_sample=300)
    assert prof["k_kmeans"] == 3  # three planted occupational skill bundles
    assert len(prof["kmeans_top"]) == 15 and prof["kmeans_sizes"].n_jobs.sum() == 594
    clf = models.run_classifier(X, jobs, skills, top_n=3)
    assert clf["metrics"]["accuracy"] > 0.95 and clf["metrics"]["macro_f1"] > 0.95
    top = clf["top_skills"]
    assert set(top[top.position_group == "Tech_Engineering"].skill) <= set(GROUPS["Tech_Engineering"])


def test_streamlit_app_pages(data, monkeypatch):
    testing = pytest.importorskip("streamlit.testing.v1")
    build_summaries.build(data, top_n=20)
    monkeypatch.setenv("SKILL_SUMMARY_DIR", str(data["summary_dir"]))
    at = testing.AppTest.from_file(str(config.ROOT / "app" / "streamlit_app.py"), default_timeout=60).run()
    assert not at.exception
    for page in at.sidebar.radio[0].options:
        at.sidebar.radio[0].set_value(page).run()
        assert not at.exception, page
