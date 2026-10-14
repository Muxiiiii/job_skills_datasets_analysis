"""Dashboard page "Course priority". Reads only <summary-dir>/course_priority/ (src/analysis/course_priority.py)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

BLUE, ORANGE, GREY = "#2a78d6", "#eb6834", "#b9b7b0"
DIM_LABEL = {"demand": "Demand", "breadth": "Breadth", "centrality": "Centrality", "accessibility": "Accessibility"}
ALL = "All occupations"
N_INTERVAL = 30


@st.cache_data(show_spinner=False)
def _csv(path: str, mtime: float) -> pd.DataFrame:
    return pd.read_csv(path)


@st.cache_data(show_spinner=False)
def _json(path: str, mtime: float) -> dict:
    return json.loads(Path(path).read_text())


def _table(base: Path, name: str) -> pd.DataFrame | None:
    p = base / name
    return _csv(str(p), p.stat().st_mtime) if p.exists() else None


def _pretty(s) -> str:
    return str(s).replace("_", " ")


def _explain(meta: dict):
    p = meta["params"]
    with st.expander("What the dimensions mean", expanded=False):
        st.markdown(
            f"""
Every skill is scored on up to four dimensions, each scaled to 0–1 ({p['normalize']}) so that **higher = higher priority**:

- **Demand** — share of deduplicated postings that mention the skill.
- **Breadth** — number of occupation groups (catch-all *Other* excluded) where the skill is over-represented (RCA > {p['rca_min']:g}).
- **Centrality** — weighted degree in the skill co-occurrence network (PMI edge weights, lift > {p['min_lift']:g},
  ≥ {p['min_co_jobs']} shared postings). PMI adjusts for prevalence, so very common skills score low here by construction; demand carries prevalence.
- **Accessibility** *(optional)* — reverse-scored entry barrier of the postings that ask for the skill:
  median minimum years of experience and share requiring a bachelor's degree or higher.

**Weights.** The headline ranking uses equal weights. *Monte Carlo*: {p['n_draws']:,} random weight vectors from a flat
Dirichlet(α = {p['alpha']:g}) give a distribution of ranks per skill (median, 5–95 % interval, probability of landing in the top 10 / top 20).
*Entropy* and *CRITIC* weights are two data-driven alternatives. Method and references: `outputs/course_priority_report*.md`.
""")


def _interval_chart(d: pd.DataFrame) -> go.Figure:
    d = d.sort_values(["mc_median_rank", "rank_equal"]).head(N_INTERVAL)
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=d.mc_median_rank, y=d.skill, mode="markers", name="Monte Carlo median rank",
        marker=dict(color=BLUE, size=9),
        error_x=dict(type="data", symmetric=False, array=d.mc_rank_p95 - d.mc_median_rank,
                     arrayminus=d.mc_median_rank - d.mc_rank_p05, color=BLUE, thickness=1.2, width=3),
        customdata=np.c_[d.mc_rank_p05, d.mc_rank_p95, d.p_top10],
        hovertemplate="%{y}<br>median rank %{x:.0f}<br>5–95%%: %{customdata[0]:.0f}–%{customdata[1]:.0f}"
                      "<br>P(top 10) %{customdata[2]:.2f}<extra></extra>"))
    fig.add_trace(go.Scatter(x=d.rank_equal, y=d.skill, mode="markers", name="Equal-weight rank",
                             marker=dict(color=ORANGE, size=7, symbol="diamond"),
                             hovertemplate="%{y}<br>equal-weight rank %{x}<extra></extra>"))
    fig.update_layout(height=max(360, 22 * len(d) + 110), margin=dict(l=10, r=20, t=40, b=10),
                      yaxis=dict(autorange="reversed", title=None),
                      xaxis=dict(title="Rank (1 = highest priority)", type="log", rangemode="tozero"),
                      legend=dict(orientation="h", y=1.05, x=0), title=None)
    return fig


def _bar(d: pd.DataFrame, x: str, fmt: str, color=BLUE, xtitle=None) -> go.Figure:
    fig = go.Figure(go.Bar(x=d[x], y=d.skill, orientation="h", marker_color=color,
                           text=d[x].map(fmt.format), textposition="outside", cliponaxis=False))
    fig.update_layout(height=max(300, 22 * len(d) + 80), margin=dict(l=10, r=50, t=10, b=10),
                      yaxis=dict(autorange="reversed", title=None), xaxis=dict(title=xtitle))
    return fig


def render(base: Path, ov: dict):
    st.title("Course priority")
    cp = base / "course_priority"
    mp = cp / "course_priority_meta.json"
    if not mp.exists():
        st.error(f"No course-priority tables in `{cp}`. Run `python -m src.analysis.course_priority` first.")
        return
    meta = _json(str(mp), mp.stat().st_mtime)
    st.caption("Which skills to prioritise in a curriculum: a composite of demand, breadth across occupations, "
               "network centrality and (optionally) accessibility, with the uncertainty that comes from choosing weights.")
    _explain(meta)

    rk, rg = _table(cp, "ranking.csv"), _table(cp, "ranking_by_group.csv")
    c = st.columns([2, 1.4, 1])
    groups = [ALL] + (sorted(rg.position_group.unique()) if rg is not None else [])
    scope = c[0].selectbox("Occupation group", groups, format_func=_pretty,
                           help="Inside a group, demand and centrality are recomputed on that group's postings; "
                                "breadth and accessibility stay corpus-wide.")
    with_acc = c[1].toggle("Include accessibility", value=True,
                           help="Off = the three-dimension robustness variant (demand, breadth, centrality).")
    top_n = c[2].slider("Rows", 10, 100, 30, step=5)
    variant = "4d" if with_acc else "3d"
    dims = meta["dims"][variant]
    d = rk if scope == ALL else rg[rg.position_group == scope]
    d = d[d.variant == variant].sort_values("rank_equal").reset_index(drop=True)
    if d.empty:
        st.info("No skills for this selection.")
        return

    tabs = st.tabs(["Ranking", "Rank intervals", "Top-10 probability", "Custom weights"])
    with tabs[0]:
        show = d.head(top_n).assign(interval=lambda x: x.mc_rank_p05.map("{:.0f}".format) + "–" + x.mc_rank_p95.map("{:.0f}".format))
        cols = ["rank_equal", "skill", "score_equal", "mc_median_rank", "interval", "p_top10", "p_top20",
                "rank_entropy", "rank_critic"] + [f"z_{k}" for k in dims]
        st.dataframe(show[cols], hide_index=True, width="stretch", column_config={
            "rank_equal": st.column_config.NumberColumn("Equal-weight rank"),
            "skill": "Skill", "score_equal": st.column_config.NumberColumn("Score", format="%.3f"),
            "mc_median_rank": st.column_config.NumberColumn("MC median rank", format="%.0f"),
            "interval": st.column_config.TextColumn("MC 5–95 % rank"),
            "p_top10": st.column_config.ProgressColumn("P(top 10)", min_value=0.0, max_value=1.0, format="%.2f"),
            "p_top20": st.column_config.ProgressColumn("P(top 20)", min_value=0.0, max_value=1.0, format="%.2f"),
            "rank_entropy": st.column_config.NumberColumn("Entropy rank"),
            "rank_critic": st.column_config.NumberColumn("CRITIC rank"),
            **{f"z_{k}": st.column_config.NumberColumn(DIM_LABEL[k], format="%.2f") for k in dims}})
        st.download_button("Download this ranking (CSV)", d.to_csv(index=False).encode(),
                           file_name=f"course_priority_{variant}_{scope.replace(' ', '_')}.csv", mime="text/csv")
        wt = _table(cp, "weights.csv" if scope == ALL else "weights_by_group.csv")
        if wt is not None:
            w = wt[wt.variant == variant] if scope == ALL else wt[(wt.variant == variant) & (wt.position_group == scope)]
            w = w.pivot_table(index="method", columns="dim", values="weight")[dims].rename(columns=DIM_LABEL)
            st.caption("Weights behind the entropy and CRITIC columns:")
            st.dataframe(w.style.format("{:.3f}"), width="content")
        ag = _table(cp, "agreement.csv" if scope == ALL else "agreement_by_group.csv")
        if ag is not None:
            a = ag[ag.variant == variant] if scope == ALL else ag[(ag.variant == variant) & (ag.position_group == scope)]
            st.caption("Agreement between the rankings (Kendall tau; size of the top-10 intersection):")
            st.dataframe(a[["method_a", "method_b", "kendall_tau", "top10_overlap"]], hide_index=True, width="content",
                         column_config={"kendall_tau": st.column_config.NumberColumn("Kendall tau", format="%.3f"),
                                        "top10_overlap": st.column_config.NumberColumn("Top-10 overlap")})
    with tabs[1]:
        st.plotly_chart(_interval_chart(d), width="stretch")
        st.caption(f"The {N_INTERVAL} skills with the best Monte Carlo median rank. Bars span the 5th–95th percentile of "
                   "the rank over all random weightings (log scale); a wide bar means the position depends heavily "
                   "on how the dimensions are weighted.")
    with tabs[2]:
        p10 = d.sort_values(["p_top10", "rank_equal"], ascending=[False, True]).head(20)
        st.plotly_chart(_bar(p10, "p_top10", "{:.2f}", xtitle="Probability of a top-10 rank"), width="stretch")
        n_stable = int((d.p_top10 >= meta["params"]["stable_p"]).sum())
        st.caption(f"Share of the {meta['params']['n_draws']:,} random weightings in which the skill ranks in the top 10. "
                   f"{n_stable} skill(s) reach {meta['params']['stable_p']:.1f} or more here.")
    with tabs[3]:
        st.write("Set your own weights; they are rescaled to sum to 1.")
        sc = st.columns(len(dims))
        raw = np.array([sc[i].slider(DIM_LABEL[k], 0.0, 1.0, 1.0 / len(dims), 0.05, key=f"w_{k}")
                        for i, k in enumerate(dims)])
        if raw.sum() == 0:
            st.warning("Give at least one dimension a weight above zero.")
        else:
            w = raw / raw.sum()
            st.caption("Normalised weights: " + ", ".join(f"{DIM_LABEL[k]} {v:.2f}" for k, v in zip(dims, w)))
            z = d[[f"z_{k}" for k in dims]].to_numpy()
            cu = d[["skill", "rank_equal"]].assign(score=z @ w)
            cu["rank"] = cu.score.rank(ascending=False, method="min").astype(int)
            cu["change_vs_equal"] = cu.rank_equal - cu["rank"]
            cu = cu.sort_values(["rank", "skill"]).head(top_n)
            left, right = st.columns([1.2, 1])
            left.plotly_chart(_bar(cu.head(20), "score", "{:.3f}", color=ORANGE, xtitle="Custom score"), width="stretch")
            right.dataframe(cu[["rank", "skill", "score", "rank_equal", "change_vs_equal"]], hide_index=True,
                            width="stretch", column_config={
                                "rank": "Rank", "skill": "Skill",
                                "score": st.column_config.NumberColumn("Score", format="%.3f"),
                                "rank_equal": "Equal-weight rank",
                                "change_vs_equal": st.column_config.NumberColumn("Places gained", format="%+d")})

    st.divider()
    st.caption(f"{meta['quality_note']} Single snapshot: no growth dimension. Rank intervals assume every weighting is "
               f"equally plausible, so they are deliberately wide. {meta['sample_note']}")
    st.caption(f"{meta['n_postings_dedup']:,} deduplicated postings · {meta['n_skills']} skills with ≥ "
               f"{meta['params']['min_skill_jobs']} postings · source {meta['source']} · generated {meta['generated_at_utc']}")
