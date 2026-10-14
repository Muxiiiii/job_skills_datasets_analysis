"""Dashboard page "Curriculum insights". Reads only <summary-dir>/curriculum/ (src/analysis/curriculum.py)."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

BLUE, ORANGE, GREY = "#2a78d6", "#eb6834", "#b9b7b0"
SEQ = ["#f0efec", "#86b6ef", "#2a78d6", "#0d366b"]
PALETTE = px.colors.qualitative.Safe
MAX_EDGES = 500  # edges drawn in the network view


@st.cache_data(show_spinner=False)
def _csv(path: str, mtime: float, **kw) -> pd.DataFrame:
    return pd.read_csv(path, **kw)


@st.cache_data(show_spinner=False)
def _json(path: str, mtime: float) -> dict:
    return json.loads(Path(path).read_text())


def _table(base: Path, name: str, **kw) -> pd.DataFrame | None:
    p = base / name
    return _csv(str(p), p.stat().st_mtime, **kw) if p.exists() else None


def _pretty(s) -> str:
    return str(s).replace("_", " ")


def _bar(df, x, y, fmt="{:.1%}", color=BLUE, tickformat=".0%", hover=None, title=None):
    fig = px.bar(df, x=x, y=y, orientation="h", hover_data=hover, title=title, text=df[x].map(fmt.format))
    fig.update_traces(marker_color=color, textposition="outside", cliponaxis=False)
    fig.update_layout(yaxis=dict(autorange="reversed", title=None), xaxis=dict(title=None, tickformat=tickformat),
                      height=max(300, 24 * len(df) + 90), margin=dict(l=10, r=50, t=50 if title else 10, b=10))
    return fig


def _network(nodes: pd.DataFrame, edges: pd.DataFrame, names: dict) -> go.Figure:
    pos = nodes.set_index("skill")[["x", "y"]]
    e = edges[edges.skill_a.isin(pos.index) & edges.skill_b.isin(pos.index)].nlargest(MAX_EDGES, "weight")
    xs, ys = [], []
    for a, b in zip(e.skill_a, e.skill_b):
        xs += [pos.at[a, "x"], pos.at[b, "x"], None]
        ys += [pos.at[a, "y"], pos.at[b, "y"], None]
    fig = go.Figure(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color=GREY, width=0.6), opacity=0.5,
                               hoverinfo="skip", showlegend=False))
    label_top = 12 if nodes.community_id.nunique() == 1 else 3
    for cid, d in nodes.groupby("community_id"):
        fig.add_trace(go.Scatter(
            x=d.x, y=d.y, mode="markers+text", name=f"{cid} · {names[cid]}",
            text=d.skill.where(d["rank"] <= label_top, ""), textposition="top center", textfont=dict(size=11),
            marker=dict(size=6 + 22 * (d.share_jobs / nodes.share_jobs.max()) ** 0.5,
                        color=PALETTE[(cid - 1) % len(PALETTE)], line=dict(color="white", width=1)),
            customdata=d[["skill", "share_jobs", "intra_degree"]],
            hovertemplate="%{customdata[0]}<br>%{customdata[1]:.1%} of postings<br>"
                          "%{customdata[2]} links inside its community<extra></extra>"))
    axis = dict(visible=False)
    fig.update_layout(height=620, xaxis=axis, yaxis=axis, margin=dict(l=10, r=10, t=10, b=10),
                      legend=dict(orientation="h", yanchor="top", y=-0.02, x=0))
    return fig


def _communities(base: Path, meta: dict):
    comm, mem = _table(base, "communities.csv"), _table(base, "community_members.csv")
    cov, edges = _table(base, "community_coverage.csv"), _table(base, "network_edges.csv")
    names = dict(zip(comm.community_id, comm.name))
    net, stab, p = meta["network"], meta["stability"], meta["params"]
    c = st.columns(4)
    c[0].metric("Skill communities", net["n_communities"])
    c[1].metric("Skills in the network", net["n_nodes"])
    c[2].metric("Edges kept", f"{net['n_edges']:,}")
    c[3].metric("Stability (mean ARI)", f"{stab['ari_mean']:.2f}",
                help=f"Mean pairwise adjusted Rand index between Louvain partitions for seeds {stab['seeds']} "
                     f"(NMI {stab['nmi_mean']:.2f}). 1 = identical partitions.")
    cid = st.selectbox("Community", comm.community_id.tolist(),
                       format_func=lambda i: f"{i} · {names[i]}  ({int(comm.set_index('community_id').at[i, 'size'])} skills)")
    m = mem[mem.community_id == cid]
    left, right = st.columns([1.15, 1])
    with left:
        st.subheader("Member skills")
        st.dataframe(m[["rank", "skill", "share_jobs", "n_jobs", "degree_centrality", "intra_degree"]],
                     hide_index=True, width="stretch", height=460, column_config={
                         "rank": "Rank", "skill": "Skill", "n_jobs": st.column_config.NumberColumn("Postings", format="localized"),
                         "share_jobs": st.column_config.NumberColumn("Share of postings", format="percent"),
                         "degree_centrality": st.column_config.NumberColumn(
                             "Centrality", format="%.2f", help="Share of the other members this skill is linked to."),
                         "intra_degree": st.column_config.NumberColumn("Links inside", help="Edges to other members.")})
    with right:
        st.subheader("Coverage by occupation group")
        d = cov[(cov.community_id == cid) & (cov.position_group != "ALL")].sort_values("coverage_any", ascending=False)
        d = d.assign(position_group=d.position_group.map(_pretty))
        st.plotly_chart(_bar(d, "coverage_any", "position_group", hover={"coverage_2plus": ":.1%", "n_jobs_in_group": ":,"}),
                        width="stretch")
        overall = cov[(cov.community_id == cid) & (cov.position_group == "ALL")].coverage_any.iat[0]
        st.caption(f"Share of a group's postings that mention at least one skill of this community "
                   f"(all postings: {overall:.1%}).")
    if st.toggle("Show network", help="Skills are linked when they appear together more often than expected."):
        scope = st.radio("Scope", ["Selected community", "All communities"], horizontal=True, label_visibility="collapsed")
        nodes = m if scope == "Selected community" else mem
        st.plotly_chart(_network(nodes, edges, names), width="stretch")
        st.caption(f"Marker size = share of postings. Showing the {MAX_EDGES} strongest links among the plotted skills. "
                   f"Edges: lift > {p['min_lift']:g} and ≥ {p['min_co_jobs']} postings together.")
    st.caption("Communities are groups of skills that employers ask for together (Louvain on the co-occurrence network). "
               "They suggest what could be bundled in one course; they do not imply a teaching order.")


def _rca(base: Path, meta: dict):
    rca = _table(base, "rca_by_group.csv")
    c = st.columns([2, 1, 1])
    g = c[0].selectbox("Occupation group", sorted(rca.position_group.unique()), format_func=_pretty)
    top_n = c[1].slider("Top N", 10, 40, 20, step=5)
    min_n = c[2].number_input("Min. postings in group", meta["params"]["rca_min_group_jobs"], 100000,
                              max(50, meta["params"]["rca_min_group_jobs"]))
    d = rca[(rca.position_group == g) & (rca.n_jobs >= min_n)].nlargest(top_n, "rca")
    if d.empty:
        st.info("No skills above the threshold.")
        return
    st.plotly_chart(_bar(d, "rca", "skill", fmt="{:.1f}×", tickformat=None,
                         hover={"share_group": ":.1%", "share_overall": ":.1%", "n_jobs": ":,"}), width="stretch")
    st.caption("RCA = share of the group's postings that mention the skill ÷ share of all postings that mention it. "
               "Above 1× the skill is over-represented in the group; high values on few postings are noisy.")
    with st.expander("Table view"):
        st.dataframe(d[["skill", "rca", "share_group", "share_overall", "n_jobs"]], hide_index=True, width="stretch",
                     column_config={"rca": st.column_config.NumberColumn("RCA", format="%.2f"),
                                    "share_group": st.column_config.NumberColumn("Share in group", format="percent"),
                                    "share_overall": st.column_config.NumberColumn("Share overall", format="percent"),
                                    "n_jobs": st.column_config.NumberColumn("Postings in group", format="localized")})


def _transitions(base: Path, meta: dict):
    sim, gaps, tr = _table(base, "group_similarity.csv"), _table(base, "transition_gaps.csv"), _table(base, "transition_transferable.csv")
    groups = sorted(sim["from"].unique())
    p = meta["params"]
    c = st.columns(2)
    a = c[0].selectbox("From", groups, format_func=_pretty)
    others = [g for g in groups if g != a]
    b = c[1].selectbox("To", others, format_func=_pretty)
    row = sim[(sim["from"] == a) & (sim["to"] == b)].iloc[0]
    rank = sim[(sim["from"] == a) & (sim["to"] != a)].cosine_share.rank(ascending=False)[row.name]
    m = st.columns(3)
    m[0].metric("Skill similarity (cosine)", f"{row.cosine_share:.2f}",
                help="Cosine between the two groups' skill-share vectors. 1 = identical skill mix.")
    m[1].metric("Similarity, RCA-weighted", f"{row.cosine_rca:.2f}",
                help="Same, with each skill weighted by how distinctive it is for the group. Stricter: ignores skills common everywhere.")
    m[2].metric(f"Closeness rank from {_pretty(a)}", f"{int(rank)} of {len(others)}")
    g = gaps[(gaps["from"] == a) & (gaps["to"] == b)]
    t = tr[(tr["from"] == a) & (tr["to"] == b)]
    left, right = st.columns([1.4, 1])
    with left:
        st.subheader(f"Skills to add (top {p['top_gap']})")
        if g.empty:
            st.info("No skill is clearly more common in the target group.")
        else:
            st.plotly_chart(_bar(g, "gap", "skill", fmt="+{:.1%}", color=ORANGE,
                                 hover={"share_from": ":.1%", "share_to": ":.1%"}), width="stretch")
            st.caption(f"Gap = share of postings in {_pretty(b)} − share in {_pretty(a)}, "
                       f"for skills in at least {p['gap_min_share_to']:.0%} of {_pretty(b)} postings.")
    with right:
        st.subheader("Transferable skills")
        if t.empty:
            st.info("No skill is common in both groups.")
        else:
            st.dataframe(t[["skill", "share_from", "share_to"]], hide_index=True, width="stretch",
                         height=min(38 * (len(t) + 1), 570), column_config={
                             "skill": "Skill",
                             "share_from": st.column_config.NumberColumn(_pretty(a), format="percent"),
                             "share_to": st.column_config.NumberColumn(_pretty(b), format="percent")})
            st.caption(f"In at least {p['transfer_min_share']:.0%} of postings on both sides.")
    with st.expander("Similarity between all occupation groups"):
        which = st.radio("Vectors", ["cosine_share", "cosine_rca"], horizontal=True,
                         format_func={"cosine_share": "Skill shares", "cosine_rca": "RCA-weighted"}.get)
        mat = sim.pivot(index="from", columns="to", values=which).loc[groups, groups]
        lab = [_pretty(x) for x in groups]
        fig = go.Figure(go.Heatmap(z=mat.values, x=lab, y=lab, colorscale=SEQ, zmin=0, zmax=1, texttemplate="%{z:.2f}",
                                   hovertemplate="%{y} → %{x}<br>cosine %{z:.2f}<extra></extra>"))
        fig.update_layout(height=560, yaxis=dict(autorange="reversed"), margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, width="stretch")
    pos = _table(base, "position_similarity.csv")
    if pos is not None:
        with st.expander("Finer view: closest search-position terms"):
            terms = sorted(pos.position_a.unique())
            s = st.selectbox("Position term", terms)
            d = pos[(pos.position_a == s) & (pos.position_b != s)].nlargest(10, "cosine_share")
            st.dataframe(d[["position_b", "group_b", "cosine_share", "n_jobs_b"]], hide_index=True, width="stretch",
                         column_config={"position_b": "Closest terms", "group_b": "Occupation group",
                                        "cosine_share": st.column_config.NumberColumn("Cosine", format="%.2f"),
                                        "n_jobs_b": st.column_config.NumberColumn("Postings", format="localized")})
            st.caption(f"Among the {len(terms)} search terms with the most postings.")


def render(base: Path, ov: dict):
    st.title("Curriculum insights")
    cur = base / "curriculum"
    if not (cur / "curriculum_meta.json").exists():
        st.error(f"No curriculum tables in `{cur}`. Run `python -m src.analysis.curriculum` first.")
        return
    mp = cur / "curriculum_meta.json"
    meta = _json(str(mp), mp.stat().st_mtime)
    tabs = st.tabs(["Skill communities", "Distinctive skills (RCA)", "Occupation transitions"])
    for tab, fn in zip(tabs, (_communities, _rca, _transitions)):
        with tab:
            fn(cur, meta)
    st.divider()
    st.caption(f"{meta['quality_note']} {meta['sample_note']} Co-occurrence shows which skills are requested "
               "together, not which must be learned first.")
    st.caption(f"{meta['n_postings_dedup']:,} deduplicated postings · {meta['n_skills']} specific skills · "
               f"source {meta['source']} · generated {meta['generated_at_utc']}")
