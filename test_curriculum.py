"""Tests for the curriculum analysis (RCA, transition gaps, Louvain communities)."""

import json

import networkx as nx
import numpy as np
import pandas as pd
import pytest

from src.analysis import build_summaries, config, curriculum
from tests.test_analysis import GROUPS, data  # noqa: F401  (shared synthetic dataset)


def test_rca_matrix():
    counts = np.array([[30, 10, 0], [10, 10, 0]])  # 2 groups x 3 skills
    rca, share_g, share_all = curriculum.rca_matrix(counts, n_group=[50, 50], n_total=100)
    assert share_g[0, 0] == pytest.approx(0.6) and share_all[0] == pytest.approx(0.4)
    assert rca[0, 0] == pytest.approx(1.5) and rca[1, 0] == pytest.approx(0.5)
    assert rca[0, 1] == pytest.approx(1.0)        # same share in both groups
    assert (rca[:, 2] == 0).all()                 # skill never seen: 0, not NaN
    # posting-weighted mean of RCA over groups is 1 for every observed skill
    assert np.average(rca[:, :2], axis=0, weights=[50, 50]) == pytest.approx([1, 1])


def test_skill_gaps_and_transferable():
    skills = ["a", "b", "c", "d"]
    frm, to = np.array([0.50, 0.02, 0.30, 0.00]), np.array([0.40, 0.20, 0.35, 0.01])
    g = curriculum.skill_gaps(frm, to, skills, min_share_to=0.03, top_n=15)
    assert g.skill.tolist() == ["b", "c"] and g["rank"].tolist() == [1, 2]   # d is below the target-share floor
    assert g.gap.tolist() == pytest.approx([0.18, 0.05])
    assert curriculum.skill_gaps(frm, to, skills, 0.03, top_n=1).skill.tolist() == ["b"]
    t = curriculum.transferable_skills(frm, to, skills, min_share=0.05)
    assert t.skill.tolist() == ["a", "c"] and t.share_min.tolist() == pytest.approx([0.40, 0.30])


def test_cosine_matrix():
    c = curriculum.cosine_matrix(np.array([[1.0, 0], [2, 0], [0, 3], [0, 0]]))
    assert c[0, 1] == pytest.approx(1) and c[0, 2] == pytest.approx(0) and c[3, 3] == 0


def test_edges_and_louvain_reproducible():
    # two 5-cliques joined by one weak edge
    edges = [(f"a{i}", f"a{j}", 2.0) for i in range(5) for j in range(i)] + \
            [(f"b{i}", f"b{j}", 2.0) for i in range(5) for j in range(i)] + [("a0", "b0", 0.1)]
    G = curriculum.build_graph(pd.DataFrame(edges, columns=["skill_a", "skill_b", "weight"]))
    p1, p2 = curriculum.louvain_partition(G, seed=7, resolution=1.0), curriculum.louvain_partition(G, seed=7, resolution=1.0)
    assert p1 == p2 and set(p1.values()) == {1, 2}
    assert len({p1[f"a{i}"] for i in range(5)}) == 1 and p1["a0"] != p1["b0"]
    stab = curriculum.partition_stability(G, seeds=[0, 1, 2], resolution=1.0)
    assert stab["ari_mean"] == pytest.approx(1.0) and stab["n_communities"] == [2, 2, 2]
    mem = curriculum.describe_communities(G, p1, seed=7)
    assert mem.groupby("community_id")["rank"].max().tolist() == [5, 5] and mem.degree_centrality.max() == 1.0

    # lift filter: pair (0,1) co-occurs far above chance, pair (0,2) below
    co = np.array([[50, 40, 5], [40, 50, 5], [5, 5, 50]])
    e = curriculum.cooccurrence_edges(co, [50, 50, 50], 200, ["x", "y", "z"], min_lift=1.5, min_co=10)
    assert e[["skill_a", "skill_b"]].values.tolist() == [["x", "y"]]
    assert e.lift[0] == pytest.approx(40 * 200 / 2500) and e.weight[0] == pytest.approx(np.log2(3.2))


def test_curriculum_end_to_end(data, tmp_path):  # noqa: F811
    out = tmp_path / "summary"
    curriculum.main(["--jobs", str(data["jobs"][0]), "--skills", str(data["skills"][0]), "--certs", str(data["certs"][0]),
                     "--summary-dir", str(out), "--report", str(tmp_path / "report.md"),
                     "--min-skill-jobs", "5", "--min-co-jobs", "5", "--vec-min-skill-jobs", "5", "--top-positions", "5"])
    cur = out / "curriculum"
    meta = json.loads((cur / "curriculum_meta.json").read_text())
    assert meta["n_postings_dedup"] == 594 and meta["network"]["n_communities"] == 3   # three planted bundles
    mem = pd.read_csv(cur / "community_members.csv")
    assert "Communication" not in set(mem.skill) and not mem.skill.str.contains("unspecified").any()
    for skills in GROUPS.values():
        assert mem[mem.skill.isin(skills)].community_id.nunique() == 1
    rca = pd.read_csv(cur / "rca_by_group.csv")
    py = rca[rca.skill == "Python"]
    assert py.position_group.tolist() == ["Tech_Engineering"] and py.rca.iat[0] == pytest.approx(3.0, rel=0.02)
    sim = pd.read_csv(cur / "group_similarity.csv")
    assert len(sim) == 9 and np.allclose(sim[sim["from"] == sim["to"]].cosine_share, 1.0)
    gaps = pd.read_csv(cur / "transition_gaps.csv")
    g = gaps[(gaps["from"] == "Tech_Engineering") & (gaps["to"] == "Healthcare_Nursing")]
    assert set(g.skill) == set(GROUPS["Healthcare_Nursing"]) and (g.gap > 0.5).all()
    tr = pd.read_csv(cur / "transition_transferable.csv")
    assert set(tr.skill) == {"Communication"}
    assert "Limitations" in (tmp_path / "report.md").read_text()
    assert config.ROOT / "outputs" not in cur.parents


def test_curriculum_page(data, monkeypatch):  # noqa: F811
    testing = pytest.importorskip("streamlit.testing.v1")
    build_summaries.build(data, top_n=20)
    curriculum.main(["--jobs", str(data["jobs"][0]), "--skills", str(data["skills"][0]), "--certs", str(data["certs"][0]),
                     "--summary-dir", str(data["summary_dir"]), "--report", str(data["summary_dir"] / "report.md"),
                     "--min-skill-jobs", "5", "--min-co-jobs", "5", "--vec-min-skill-jobs", "5", "--top-positions", "5"])
    monkeypatch.setenv("SKILL_SUMMARY_DIR", str(data["summary_dir"]))
    at = testing.AppTest.from_file(str(config.ROOT / "app" / "streamlit_app.py"), default_timeout=60).run()
    at.sidebar.radio[0].set_value("Curriculum insights").run()
    assert not at.exception and not at.error
    assert [t.label for t in at.tabs] == ["Skill communities", "Distinctive skills (RCA)", "Occupation transitions"]
    at.toggle[0].set_value(True).run()            # network view
    assert not at.exception
    frm = next(s for s in at.selectbox if s.label == "From")
    frm.set_value("Tech_Engineering").run()
    assert not at.exception and any(m.label.startswith("Skill similarity") for m in at.metric)
