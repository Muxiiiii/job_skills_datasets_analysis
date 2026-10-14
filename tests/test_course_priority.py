"""Tests for the course-priority composite (weights, rank distributions, end-to-end, dashboard page)."""

import json

import numpy as np
import pandas as pd
import pytest

from src.analysis import build_summaries, config, course_priority as cp
from tests.test_analysis import GROUPS, data  # noqa: F401  (shared synthetic dataset)


def test_normalize():
    X = np.array([[0.0, 5, 1], [5, 5, 3], [10, 5, 2]])
    Z = cp.normalize(X)
    assert Z[:, 0].tolist() == pytest.approx([0, 0.5, 1]) and (Z[:, 1] == 0).all()   # constant column -> 0
    P = cp.normalize(X, "percentile")
    assert P[:, 2].tolist() == pytest.approx([0, 1, 0.5]) and P.min() >= 0 and P.max() <= 1


def test_dirichlet_weights_sum_to_one():
    W = cp.dirichlet_weights(2000, 4, alpha=1.0, seed=42)
    assert W.shape == (2000, 4) and (W >= 0).all()
    assert np.allclose(W.sum(axis=1), 1.0)
    assert np.allclose(W.mean(axis=0), 0.25, atol=0.02)          # flat Dirichlet: mean weight 1/k
    assert np.array_equal(W, cp.dirichlet_weights(2000, 4, seed=42))   # fixed seed -> reproducible


def test_entropy_weights_known_example():
    # column 0: one non-zero value -> entropy 0, d = 1; column 1: (1, 1, 0) -> e = ln2 / ln3
    w = cp.entropy_weights(np.array([[1.0, 1], [0, 1], [0, 0]]))
    d1 = 1 - np.log(2) / np.log(3)
    assert w == pytest.approx([1 / (1 + d1), d1 / (1 + d1)])
    # a constant column carries no information
    assert cp.entropy_weights(np.array([[1.0, 1], [1, 2], [1, 3]])) == pytest.approx([0, 1])
    assert cp.entropy_weights(np.array([[0.2, 0.5, 0.1], [0.7, 0.1, 0.9]])).sum() == pytest.approx(1)


def test_critic_weights_known_example():
    # a and b identical (r = 1), c the mirror image (r = -1); equal standard deviations
    # conflict: a = 0 + 2 = 2, b = 2, c = 2 + 2 = 4  ->  weights (0.25, 0.25, 0.5)
    Z = np.array([[0.0, 0, 1], [0.5, 0.5, 0.5], [1, 1, 0]])
    assert cp.critic_weights(Z) == pytest.approx([0.25, 0.25, 0.5])
    # a constant column gets weight 0
    w = cp.critic_weights(np.array([[0.0, 1, 0.3], [1, 1, 0.9], [0.5, 1, 0.1]]))
    assert w[1] == 0 and w.sum() == pytest.approx(1)


def test_rank_distribution_probabilities():
    rng = np.random.default_rng(0)
    Z = rng.random((30, 4))
    Z[0] = 1.0                                        # dominates every other row under any weights
    d = cp.rank_distribution(Z, cp.dirichlet_weights(500, 4), top_k=(10, 20))
    for c in ("p_top10", "p_top20"):
        assert d[c].between(0, 1).all()
    assert (d.p_top20 >= d.p_top10).all()
    assert d.p_top10.sum() >= 10 * 0.999              # ten rows (or more, with ties) are in the top 10 each draw
    assert d.loc[0, "mc_median_rank"] == 1 and d.loc[0, "p_top10"] == 1
    assert (d.mc_rank_p05 <= d.mc_median_rank).all() and (d.mc_median_rank <= d.mc_rank_p95).all()
    assert cp.rank_desc(np.array([0.3, 0.9, 0.3, 0.1])).tolist() == [2, 1, 2, 4]


def test_agreement_identical_and_reversed():
    r = np.arange(1, 13)
    a = cp.agreement({"equal": r, "same": r.copy(), "rev": r[::-1].copy()}, k=10)
    same = a[(a.method_a == "equal") & (a.method_b == "same")].iloc[0]
    rev = a[(a.method_a == "equal") & (a.method_b == "rev")].iloc[0]
    assert same.kendall_tau == pytest.approx(1) and same.top10_overlap == 10
    assert rev.kendall_tau == pytest.approx(-1) and rev.top10_overlap == 8


def _run(data, out, report):  # noqa: F811
    cp.main(["--jobs", str(data["jobs"][0]), "--skills", str(data["skills"][0]), "--certs", str(data["certs"][0]),
             "--summary-dir", str(out), "--report", str(report), "--min-skill-jobs", "5", "--min-co-jobs", "5",
             "--group-min-skill-jobs", "5", "--n-draws", "300"])


def test_course_priority_end_to_end(data, tmp_path):  # noqa: F811
    out, report = tmp_path / "summary", tmp_path / "report.md"
    _run(data, out, report)
    d = out / "course_priority"
    meta = json.loads((d / "course_priority_meta.json").read_text())
    assert meta["n_postings_dedup"] == 594 and meta["n_skills"] == 13            # 12 group skills + Communication
    dims = pd.read_csv(d / "dimensions.csv")
    assert not dims.skill.str.contains("unspecified").any()
    com = dims.set_index("skill").loc["Communication"]
    assert com.demand == pytest.approx(1.0) and com.breadth == 0 and com.centrality == 0   # in every posting: no lift
    assert dims.set_index("skill").loc["Python", "breadth"] == 1
    for c in cp.DIMS_4:
        assert dims[f"z_{c}"].between(0, 1).all()
    rk = pd.read_csv(d / "ranking.csv")
    assert set(rk.variant) == {"4d", "3d"} and (rk.groupby("variant").size() == 13).all()
    assert rk[["p_top10", "p_top20"]].stack().between(0, 1).all()
    w = pd.read_csv(d / "weights.csv")
    assert np.allclose(w.groupby(["variant", "method"]).weight.sum(), 1.0)
    assert set(w[w.variant == "3d"].dim) == set(cp.DIMS_3)
    ag = pd.read_csv(d / "agreement.csv")
    assert len(ag) == 12 and ag.kendall_tau.between(-1, 1).all()
    g = pd.read_csv(d / "ranking_by_group.csv")
    assert set(g.position_group) == set(GROUPS)
    tech = g[(g.position_group == "Tech_Engineering") & (g.variant == "4d")]
    assert set(GROUPS["Tech_Engineering"]) <= set(tech.skill) and "Nursing" not in set(tech.skill)
    text = report.read_text()
    assert "Kendall" in text and "Saisana" in text and "Limitations" in text


def test_course_priority_page(data, tmp_path, monkeypatch):  # noqa: F811
    testing = pytest.importorskip("streamlit.testing.v1")
    base = tmp_path / "summary"
    build_summaries.build({**data, "summary_dir": base}, top_n=20)
    _run(data, base, tmp_path / "report.md")
    monkeypatch.setenv("SKILL_SUMMARY_DIR", str(base))
    at = testing.AppTest.from_file(str(config.ROOT / "app" / "streamlit_app.py"), default_timeout=60).run()
    at.sidebar.radio[0].set_value("Course priority").run()
    assert not at.exception and not at.error
    assert [t.label for t in at.tabs] == ["Ranking", "Rank intervals", "Top-10 probability", "Custom weights"]
    at.toggle[0].set_value(False).run()                       # three-dimension variant
    assert not at.exception and len(at.slider) == 1 + 3       # rows + three weight sliders
    at.selectbox[0].set_value("Tech_Engineering").run()
    assert not at.exception
    for s in at.slider[1:]:
        s.set_value(0.0)
    at.run()
    assert not at.exception and any("at least one dimension" in w.value for w in at.warning)
