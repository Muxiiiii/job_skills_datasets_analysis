"""Skill-demand dashboard. Reads only the small summary tables.

    streamlit run app/streamlit_app.py
    SKILL_SUMMARY_DIR=outputs/summary/full streamlit run app/streamlit_app.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIR = os.environ.get("SKILL_SUMMARY_DIR", "outputs/summary/pilot")
BLUE, ORANGE = "#2a78d6", "#eb6834"
SEQ = ["#f0efec", "#86b6ef", "#2a78d6", "#0d366b"]
DIV = ["#1c5cab", "#86b6ef", "#f0efec", "#f2a98a", "#c44a1c"]
DIMS = ["position_group", "search_country", "job_level"]
EDU_ORDER = ["high_school", "associate", "bachelor", "master", "phd", "professional_doctorate"]
BA_PLUS = ["bachelor", "master", "phd", "professional_doctorate"]

st.set_page_config(page_title="LinkedIn skill demand", page_icon="📊", layout="wide")


def resolve(d: str) -> Path:
    p = Path(d)
    return p if p.is_absolute() else ROOT / p


@st.cache_data(show_spinner=False)
def read_csv(path: str, mtime: float) -> pd.DataFrame:
    return pd.read_csv(path)


@st.cache_data(show_spinner=False)
def read_json(path: str, mtime: float) -> dict:
    return json.loads(Path(path).read_text())


def table(base: Path, name: str) -> pd.DataFrame | None:
    p = base / name
    return read_csv(str(p), p.stat().st_mtime) if p.exists() else None


def pretty(s) -> str:
    return str(s).replace("_", " ")


def bar(df, x, y, title=None, color=BLUE, pct=True, height=None, hover=None):
    fig = px.bar(df, x=x, y=y, orientation="h", title=title, hover_data=hover,
                 text=df[x].map(lambda v: f"{v:.1%}" if pct else f"{v:,.0f}"))
    fig.update_traces(marker_color=color, textposition="outside", cliponaxis=False)
    fig.update_layout(yaxis=dict(autorange="reversed", title=None), xaxis=dict(title=None, tickformat=".0%" if pct else None),
                      height=height or max(320, 24 * len(df) + 90), margin=dict(l=10, r=40, t=50 if title else 10, b=10))
    return fig


def filt(df: pd.DataFrame, sel: dict) -> pd.DataFrame:
    for dim, vals in sel.items():
        if vals:
            df = df[df[dim].isin(vals)]
    return df


# ------------------------------------------------------------------------------- pages
def page_overview(base, ov):
    st.title("LinkedIn skill demand — overview")
    c = st.columns(4)
    c[0].metric("Postings (deduplicated)", f"{ov['n_postings_dedup']:,}", f"-{ov['dup_share']:.1%} duplicates removed", delta_color="off")
    c[1].metric("Specific skills tracked", ov["n_distinct_skills_specific"])
    c[2].metric("Median skills per posting", f"{ov['skills_per_job_median_specific']:.0f}")
    c[3].metric("Postings with ≥1 skill", f"{ov['share_jobs_with_any_specific_skill']:.1%}")
    c = st.columns(4)
    c[0].metric("State a degree", f"{ov['share_jobs_edu_stated']:.1%}")
    c[1].metric("State years of experience", f"{ov['share_jobs_yoe_stated']:.1%}")
    c[2].metric("Mention a certificate", f"{ov['share_jobs_any_cert']:.1%}")
    c[3].metric("High-confidence skill mentions", f"{ov['share_skill_rows_high_conf']:.1%}")
    jd = table(base, "jobs_by_dim.csv")
    cols = st.columns(3)
    for col, dim, title in zip(cols, DIMS, ["By occupation group", "By country", "By level"]):
        d = jd[jd.dim == dim].assign(value=lambda x: x.value.map(pretty))
        col.plotly_chart(bar(d, "share_jobs", "value", title, hover=["n_jobs"]), width="stretch")
    freq = table(base, "skill_freq_overall.csv").head(15)
    st.plotly_chart(bar(freq, "share_jobs", "skill", "Top 15 skills (share of postings)", hover=["n_jobs"]), width="stretch")
    st.caption(ov["quality_note"])
    st.caption(f"Source files: {len(ov['inputs']['jobs'])} · generated {ov['generated_at_utc']}")


def page_ranking(base, ov):
    st.title("Skill ranking")
    cube, jobs = table(base, "skill_freq_cube.csv"), table(base, "jobs_cube.csv")
    meta = table(base, "skill_meta.csv")
    f = st.columns([2, 2, 1.3, 1.3])
    sel = {
        "position_group": f[0].multiselect("Occupation group", sorted(jobs.position_group.unique()), format_func=pretty),
        "search_country": f[1].multiselect("Country", sorted(jobs.search_country.unique())),
        "job_level": f[2].multiselect("Job level", sorted(jobs.job_level.unique())),
    }
    kind = f[3].selectbox("Skill type", ["all", "soft", "hard", "tool"])
    g = st.columns([1.3, 1.3, 3])
    hc = g[0].toggle("High-confidence only", help="Both LinkedIn's skill list and the description agree (precision≈0.93, lower coverage).")
    top_n = g[1].slider("Top N", 10, 100, 30, step=5)
    search = g[2].text_input("Search skill", placeholder="e.g. python")

    n_den = int(filt(jobs, sel).n_jobs.sum())
    if n_den == 0:
        st.warning("No postings match these filters.")
        return
    col = "n_jobs_hc" if hc else "n_jobs"
    d = filt(cube, sel).groupby("skill", as_index=False)[["n_jobs", "n_jobs_hc"]].sum().merge(meta, on="skill", how="left")
    d["share"] = d[col] / n_den
    overall = table(base, "skill_freq_overall.csv").set_index("skill")["share_jobs_hc" if hc else "share_jobs"]
    d["lift_vs_overall"] = d.share / d.skill.map(overall)
    if kind != "all":
        d = d[d.skill_type == kind]
    d = d.sort_values(col, ascending=False)
    d.insert(0, "rank", range(1, len(d) + 1))
    if search:
        d = d[d.skill.str.contains(search, case=False, regex=False)]
    st.caption(f"{n_den:,} postings match · share = postings mentioning the skill ÷ matching postings"
               + (" · high-confidence mentions only" if hc else ""))
    show = d.head(top_n)
    if show.empty:
        st.info("No skills match.")
        return
    st.plotly_chart(bar(show, "share", "skill", color=ORANGE if hc else BLUE,
                        hover={"rank": True, col: ":,", "lift_vs_overall": ":.2f", "skill_type": True, "domain": True}),
                    width="stretch")
    with st.expander("Table view / download"):
        st.dataframe(d[["rank", "skill", "skill_type", "domain", "n_jobs", "n_jobs_hc", "share", "lift_vs_overall"]],
                     hide_index=True, width="stretch",
                     column_config={"share": st.column_config.NumberColumn(format="percent"),
                                    "lift_vs_overall": st.column_config.NumberColumn(format="%.2f")})
    st.caption(ov["quality_note"])


def page_cooccurrence(base, ov):
    st.title("Skill co-occurrence")
    files = sorted(base.glob("skill_cooccurrence_top*.csv"))
    if not files:
        st.info("No co-occurrence table found.")
        return
    co = read_csv(str(files[0]), files[0].stat().st_mtime)
    freq = table(base, "skill_freq_overall.csv")
    tab1, tab2 = st.tabs(["Partners of one skill", "Heatmap"])
    with tab1:
        skills = [s for s in freq.skill if s in set(co.skill_a) | set(co.skill_b)]
        c = st.columns([2, 1, 1])
        s = c[0].selectbox("Skill", skills, index=skills.index("Python") if "Python" in skills else 0)
        min_co = c[1].number_input("Min. postings together", 1, 100000, 100)
        by = c[2].radio("Sort by", ["lift", "n_co"], horizontal=True,
                        format_func={"lift": "lift", "n_co": "postings together"}.get)
        a = co[co.skill_a == s].rename(columns={"skill_b": "partner", "n_b": "n_partner"})
        b = co[co.skill_b == s].rename(columns={"skill_a": "partner", "n_a": "n_partner"})
        d = pd.concat([a, b])[["partner", "n_co", "n_partner", "lift", "jaccard"]]
        d = d[d.n_co >= min_co].sort_values(by, ascending=False).head(25)
        if d.empty:
            st.info("No partners above the threshold.")
        else:
            st.plotly_chart(bar(d, by, "partner", pct=False, hover={"n_co": ":,", "lift": ":.2f", "jaccard": ":.3f"}),
                            width="stretch")
            st.caption("Lift = how many times more often the two skills appear together than expected if independent (1 = independent).")
            with st.expander("Table view"):
                st.dataframe(d, hide_index=True, width="stretch")
    with tab2:
        n = st.slider("Top N skills", 10, 60, 30, step=5)
        top = freq.head(n).skill.tolist()
        d = co[co.skill_a.isin(top) & co.skill_b.isin(top)]
        m = pd.DataFrame(float("nan"), index=top, columns=top)
        for r in d.itertuples():
            m.loc[r.skill_a, r.skill_b] = m.loc[r.skill_b, r.skill_a] = r.lift
        import numpy as np
        fig = go.Figure(go.Heatmap(z=np.log2(m.values.astype(float)), x=top, y=top, colorscale=DIV, zmid=0, zmin=-2.5, zmax=2.5,
                                   customdata=m.values, hovertemplate="%{y} + %{x}<br>lift %{customdata:.2f}×<extra></extra>",
                                   colorbar=dict(title="lift", tickvals=[-2, -1, 0, 1, 2], ticktext=["¼×", "½×", "1×", "2×", "4×"])))
        fig.update_layout(height=780, yaxis=dict(autorange="reversed"), margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, width="stretch")
    st.caption(ov["quality_note"])


def page_edu_yoe(base, ov):
    st.title("Education and experience")
    edu, yoe = table(base, "edu_dist.csv"), table(base, "yoe_dist.csv")
    f = st.columns(3)
    sel = {"position_group": f[0].multiselect("Occupation group", sorted(edu.position_group.unique()), format_func=pretty),
           "search_country": f[1].multiselect("Country", sorted(edu.search_country.unique())),
           "job_level": f[2].multiselect("Job level", sorted(edu.job_level.unique()))}
    e, y = filt(edu, sel), filt(yoe, sel)
    tot = e.n_jobs.sum()
    if tot == 0:
        st.warning("No postings match these filters.")
        return
    stated = e[e.edu_required != "not_stated"]
    ys = y.dropna(subset=["yoe_min_overall"])
    c = st.columns(4)
    c[0].metric("Postings", f"{tot:,}")
    c[1].metric("State a degree", f"{stated.n_jobs.sum() / tot:.1%}")
    c[2].metric("State experience", f"{ys.n_jobs.sum() / tot:.1%}")
    if len(ys):
        med = ys.sort_values("yoe_min_overall").assign(c=lambda d: d.n_jobs.cumsum())
        c[3].metric("Median min. years", f"{med[med.c >= med.n_jobs.sum() / 2].yoe_min_overall.iloc[0]:.0f}")
    left, right = st.columns(2)
    if len(stated):
        d = stated.groupby("edu_required").n_jobs.sum().reindex(EDU_ORDER).fillna(0).reset_index()
        d["share"] = d.n_jobs / d.n_jobs.sum()
        d["edu_required"] = d.edu_required.map(pretty)
        left.plotly_chart(bar(d, "share", "edu_required", "Required degree (among postings stating one)", hover=["n_jobs"]),
                          width="stretch")
    if len(ys):
        d = ys.assign(years=ys.yoe_min_overall.clip(upper=10).round().astype(int)).groupby("years").n_jobs.sum().reindex(range(11)).fillna(0).reset_index()
        d["share"] = d.n_jobs / d.n_jobs.sum()
        d["label"] = d.years.map(lambda v: "10+" if v == 10 else str(v))
        fig = px.bar(d, x="label", y="share", title="Minimum years of experience (among postings stating one)", hover_data=["n_jobs"])
        fig.update_traces(marker_color=BLUE)
        fig.update_layout(xaxis=dict(title="years", type="category"), yaxis=dict(title=None, tickformat=".0%"), height=420)
        right.plotly_chart(fig, width="stretch")
    if len(stated):
        g = stated.assign(ba=stated.edu_required.isin(BA_PLUS) * stated.n_jobs).groupby("position_group")[["ba", "n_jobs"]].sum()
        g = g.assign(share=g.ba / g.n_jobs).sort_values("share", ascending=False).reset_index()
        g["position_group"] = g.position_group.map(pretty)
        st.plotly_chart(bar(g, "share", "position_group", "Share requiring a bachelor's or higher, by group (among postings stating a degree)",
                            hover=["n_jobs"]), width="stretch")
    st.caption("Quality: edu_required accuracy≈0.86, years-of-experience accuracy≈0.84 on 50 unseen postings. Errors are mostly "
               "missed values, so 'not stated' is over-counted; shares are among postings with a value.")


def page_certs(base, ov):
    st.title("Certificates and licences")
    cert, by = table(base, "cert_occurrence.csv"), table(base, "cert_by_position_group.csv")
    groups = ["All groups"] + sorted(by.position_group.unique())
    c = st.columns([2, 1])
    g = c[0].selectbox("Occupation group", groups, format_func=pretty)
    n = c[1].slider("Top N", 5, 40, 20)
    d = cert if g == "All groups" else by[by.position_group == g]
    d = d.sort_values("n_jobs", ascending=False).head(n)
    st.plotly_chart(bar(d, "share_jobs", "cert", hover=["n_jobs"]), width="stretch")
    with st.expander("Table view"):
        st.dataframe(d, hide_index=True, width="stretch")
    st.caption("Only single-certificate occurrence rates are shown: per-posting certificate sets are unreliable "
               "(exact-set accuracy 0.56). Counts mix required and preferred mentions.")


def page_models(base, ov):
    st.title("Model results")
    mdir = base / "models"
    if not (mdir / "model_metrics.json").exists():
        st.info("No model outputs found. Run `python -m src.analysis.models`.")
        return
    p = mdir / "model_metrics.json"
    m = read_json(str(p), p.stat().st_mtime)
    t = lambda n: read_csv(str(mdir / n), (mdir / n).stat().st_mtime)  # noqa: E731
    st.caption(f"{m['n_jobs']:,} postings with ≥{m['min_skills']} specific skills × {m['n_skills']} skills · {m['source']}")
    tab1, tab2 = st.tabs(["Skill profiles (NMF / KMeans)", "Predicting occupation group"])
    with tab1:
        method = st.radio("Method", ["NMF topics", "KMeans clusters"], horizontal=True)
        key, label = ("nmf", "topic") if method.startswith("NMF") else ("kmeans", "cluster")
        top, sizes = t(f"{key}_top.csv"), t(f"{key}_sizes.csv").sort_values("n_jobs", ascending=False)
        st.caption(f"k = {m['k_' + key]} · chosen by " + ("topic coherence" if key == "nmf" else "cosine silhouette")
                   + " over k ∈ " + str(m["k_grid"]) + ". Both criteria are monotone over this range, so k is a convenient resolution, not a discovered number.")
        cols = st.columns(3)
        for i, r in enumerate(sizes.itertuples()):
            k = getattr(r, label)
            with cols[i % 3].container(border=True):
                names = top[top[label] == k].sort_values("rank").skill.tolist()
                st.markdown(f"**{label.title()} {k}: {' · '.join(names[:3])}**")
                st.caption(f"{r.n_jobs:,} postings ({r.share_jobs:.1%}) — {r.top_position_groups}")
                st.write(", ".join(names))
        with st.expander("k selection table"):
            st.dataframe(t("k_selection.csv"), hide_index=True, width="stretch")
    with tab2:
        cm = m["classifier"]
        c = st.columns(4)
        c[0].metric("Accuracy", f"{cm['accuracy']:.3f}", f"baseline {cm['baseline_majority_accuracy']:.3f}", delta_color="off")
        c[1].metric("Macro-F1", f"{cm['macro_f1']:.3f}", f"baseline {cm['baseline_majority_macro_f1']:.3f}", delta_color="off")
        c[2].metric("Train / test", f"{cm['n_train']:,} / {cm['n_test']:,}")
        c[3].metric("Classes × features", f"{cm['n_classes']} × {cm['n_features']}")
        st.caption("Logistic regression on TF-IDF skill indicators, stratified split, balanced class weights; the catch-all 'Other' group is excluded.")
        pc = t("clf_per_class.csv").sort_values("f1", ascending=False).assign(position_group=lambda d: d.position_group.map(pretty))
        left, right = st.columns(2)
        fig = bar(pc, "f1", "position_group", "F1 by group (test set)", pct=False, hover=["precision", "recall", "support"])
        fig.update_traces(text=pc.f1.map("{:.2f}".format))
        left.plotly_chart(fig, width="stretch")
        conf = t("clf_confusion.csv")
        mat = conf.pivot(index="true", columns="predicted", values="n")
        mat = mat.div(mat.sum(axis=1), axis=0)
        fig = px.imshow(mat.rename(index=pretty, columns=pretty), color_continuous_scale=SEQ, zmin=0, zmax=1, aspect="auto",
                        title="Confusion matrix (row-normalised)", labels=dict(color="share of true"))
        fig.update_layout(height=max(320, 24 * len(pc) + 90) + 60)
        right.plotly_chart(fig, width="stretch")
        ts = t("clf_top_skills.csv")
        grp = st.selectbox("Most predictive skills for", sorted(ts.position_group.unique()), format_func=pretty)
        d = ts[ts.position_group == grp].sort_values("rank")
        fig = bar(d, "coef", "skill", pct=False)
        fig.update_traces(text=d.coef.map("{:.2f}".format))
        st.plotly_chart(fig, width="stretch")
    st.caption(ov["quality_note"])


def page_quality(base, ov):
    st.title("Data quality")
    q = ov["quality"]
    st.markdown("Measured on **50 fresh postings** never seen during rule development, labelled blind before running the pipeline.")
    rows = [
        ("Skills (all)", f"precision {q['skill_precision']:.2f} · recall {q['skill_recall']:.2f}", "Rankings and group comparisons — not per-posting lists"),
        ("Skills (high-confidence, two sources agree)", f"precision {q['skill_precision_high_conf']:.2f}", "Conservative view; lower coverage"),
        ("Required education", f"accuracy {q['edu_required_acc']:.2f}", "Usable; often not stated"),
        ("Years of experience", f"accuracy {q['yoe_overall_acc']:.2f}", "Usable; misses are mostly blanks"),
        ("Certificates (exact set per posting)", f"accuracy {q['certs_exact_set_acc']:.2f}", "Not usable as a set — single-certificate rates only"),
        ("job_family_pred", f"accuracy {q['job_family_pred_acc']:.2f}", "Experimental; not used. Grouping uses search_position → position_group"),
    ]
    st.dataframe(pd.DataFrame(rows, columns=["Field", "Fresh-50 result", "How to use it"]), hide_index=True, width="stretch")
    st.subheader("Defaults used in every view")
    st.markdown(
        "- **Deduplication:** one posting per `dup_group_id`.\n"
        "- **Skills:** generic labels (`is_generic`, `(unspecified)`) are excluded.\n"
        "- **Shares:** postings mentioning the item ÷ deduplicated postings in the selected group.\n"
        "- **High-confidence:** the skill appears both in LinkedIn's skill list and in the description text.")
    st.subheader("This dataset")
    n = ov["n_postings_dedup"]
    mix = pd.DataFrame({"country": list(ov["by_country"]), "postings": list(ov["by_country"].values())})
    mix["share"] = mix.postings / n
    st.dataframe(mix, hide_index=True, column_config={"share": st.column_config.NumberColumn(format="percent")})
    if len(ov["inputs"]["jobs"]) > 1 or "chunk" in ov["inputs"]["jobs"][0]:
        st.warning("These summaries come from a **partial slice** of the full run, which processes postings in URL order. "
                   "Australia, Canada and the UK are essentially complete; the US covers only job titles early in the alphabet "
                   "and is under-weighted (~32% here vs ~85% of the corpus). Treat US and overall figures as provisional.")
    with st.expander("Input files"):
        st.json(ov["inputs"])


PAGES = {"Overview": page_overview, "Skill ranking": page_ranking, "Co-occurrence": page_cooccurrence,
         "Education & experience": page_edu_yoe, "Certificates": page_certs, "Model results": page_models,
         "Data quality": page_quality}


def main():
    st.sidebar.header("LinkedIn skill demand")
    page = st.sidebar.radio("Page", list(PAGES), label_visibility="collapsed")
    with st.sidebar.expander("Data source"):
        d = st.text_input("Summary directory", DEFAULT_DIR, help="Folder produced by src/analysis/build_summaries.py")
    base = resolve(d)
    if not (base / "overview.json").exists():
        st.error(f"No summary tables in `{base}`. Run `python -m src.analysis.build_summaries` first.")
        st.stop()
    p = base / "overview.json"
    ov = read_json(str(p), p.stat().st_mtime)
    st.sidebar.caption(f"{ov['n_postings_dedup']:,} postings · skill precision≈{ov['quality']['skill_precision']:.2f}")
    PAGES[page](base, ov)


main()
