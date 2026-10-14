"""EDA figures + markdown report, built only from the summary tables.

    python -m src.analysis.eda                                   # pilot summaries
    python -m src.analysis.eda --preset full                     # -> outputs/figures_full/, eda_report_full.md
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm

from src.analysis.config import PRESETS, ROOT

BLUE, ORANGE, INK, INK2, MUTED, GRID, SURFACE = (
    "#2a78d6", "#eb6834", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#fcfcfb")
SEQ = LinearSegmentedColormap.from_list("seq_blue", ["#f0efec", "#86b6ef", "#2a78d6", "#0d366b"])
DIV = LinearSegmentedColormap.from_list("div", ["#1c5cab", "#86b6ef", "#f0efec", "#f2a98a", "#c44a1c"])
EDU_ORDER = ["high_school", "associate", "bachelor", "master", "phd", "professional_doctorate"]
EDU_LABEL = {"high_school": "High school", "associate": "Associate", "bachelor": "Bachelor",
             "master": "Master", "phd": "PhD", "professional_doctorate": "Prof. doctorate"}
CAPTION = ("Quality: skill extraction precision≈0.66, recall≈0.58 on 50 unseen postings "
           "(high-confidence two-source subset ≈0.93). Suitable for ranking, not per-posting lists.")

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "font.size": 10, "axes.edgecolor": "#c3c2b7", "axes.labelcolor": INK2,
    "xtick.color": MUTED, "ytick.color": INK2, "axes.titlecolor": INK, "axes.titleweight": "bold",
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": False,
    "axes.titlelocation": "left", "figure.dpi": 110,
})


def pretty(s: str) -> str:
    return str(s).replace("_", " ")


def pct(x: float, d: int = 1) -> str:
    return f"{100 * x:.{d}f}%"


class Report:
    def __init__(self, fig_dir: Path, report_path: Path):
        self.fig_dir, self.report_path, self.sections = fig_dir, report_path, []
        fig_dir.mkdir(parents=True, exist_ok=True)

    def save(self, fig, name: str, title: str, finding: str, caption: str = CAPTION):
        fig.text(0.01, 0.005, caption, fontsize=7.5, color=MUTED, ha="left", va="bottom", wrap=True)
        path = self.fig_dir / f"{name}.png"
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        rel = Path(*path.relative_to(self.report_path.parent).parts) if path.is_relative_to(self.report_path.parent) else path
        self.sections.append(f"## {title}\n\n**Finding.** {finding}\n\n![{title}]({rel.as_posix()})\n\n*{caption}*\n")
        print(f"  {path.name}: {finding}")


def hbar(ax, labels, values, color=BLUE, fmt=pct, xlabel="share of postings"):
    y = np.arange(len(labels))[::-1]
    ax.barh(y, values, color=color, height=0.68, zorder=2)
    ax.set_yticks(y, labels)
    ax.xaxis.grid(True, color=GRID, lw=0.6, zorder=0)
    ax.set_axisbelow(True)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.xaxis.set_major_formatter(lambda v, _: fmt(v, 0))
    ax.set_xlabel(xlabel)
    for yi, v in zip(y, values):
        ax.text(v, yi, " " + fmt(v), va="center", ha="left", fontsize=8, color=INK2)
    ax.set_xlim(0, max(values) * 1.14)


def fig_overview(S, ov, rep):
    jd = S["jobs_by_dim"]
    fig, axes = plt.subplots(1, 3, figsize=(15, 5), gridspec_kw={"width_ratios": [1, 1.4, 0.8]})
    for ax, dim, title in zip(axes, ["search_country", "position_group", "job_level"],
                              ["Postings by country", "Postings by occupation group", "Postings by level"]):
        d = jd[jd.dim == dim].sort_values("n_jobs", ascending=False)
        hbar(ax, [pretty(v) for v in d.value], d.share_jobs.to_numpy())
        ax.set_title(title)
    fig.suptitle(f"Dataset overview — {ov['n_postings_dedup']:,} deduplicated postings "
                 f"({ov['n_postings_raw']:,} raw)", x=0.01, ha="left", fontsize=13, fontweight="bold")
    fig.tight_layout(rect=(0, 0.04, 1, 0.95))
    c = ov["by_country"]
    top_c = max(c, key=c.get)
    rep.save(fig, "01_overview", "Dataset overview",
             f"{ov['n_postings_dedup']:,} postings remain after removing {pct(ov['dup_share'])} duplicates; "
             f"{pct(ov['share_jobs_with_any_specific_skill'])} have at least one specific skill "
             f"(median {ov['skills_per_job_median_specific']:.0f} per posting), while only "
             f"{pct(ov['share_jobs_edu_stated'])} state a degree and {pct(ov['share_jobs_yoe_stated'])} state years of experience. "
             f"{top_c} is the largest country in this slice ({pct(c[top_c] / ov['n_postings_dedup'])}).")


def fig_top_skills(S, rep, n=30):
    f = S["freq"].head(n)
    fig, ax = plt.subplots(figsize=(10, 9))
    hbar(ax, f.skill, f.share_jobs.to_numpy())
    y = np.arange(len(f))[::-1]
    ax.scatter(f.share_jobs_hc, y, s=34, color=ORANGE, zorder=3, edgecolor=SURFACE, linewidth=1.2,
               label="high-confidence subset (both sources agree)")
    ax.barh([], [], color=BLUE, label="all extracted")
    ax.legend(loc="lower right", frameon=False)
    ax.set_title(f"Top {n} skills by share of postings (generic labels excluded)")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    soft = int((f.head(10).skill_type == "soft").sum())
    hard1 = f[f.skill_type != "soft"].iloc[0]
    rep.save(fig, "02_top30_skills", f"Top {n} skills overall",
             f"{f.skill[0]} ({pct(f.share_jobs[0])}) and {f.skill[1]} ({pct(f.share_jobs[1])}) lead; "
             f"{soft} of the top 10 are soft skills, and the most common non-soft skill is "
             f"{hard1.skill} ({pct(hard1.share_jobs)}). The high-confidence ranking keeps the same top 2.")


def fig_by_group(S, rep, n=15):
    g = S["by_group"]
    groups = g.groupby("position_group").n_jobs_in_group.first().sort_values(ascending=False).index.tolist()
    ncol = 4
    nrow = int(np.ceil(len(groups) / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(22, 5.2 * nrow))
    for ax, grp in zip(axes.flat, groups):
        d = g[g.position_group == grp].head(n)
        hbar(ax, d.skill, d.share_jobs.to_numpy(), xlabel="")
        ax.set_title(f"{pretty(grp)} (n={int(d.n_jobs_in_group.iloc[0]):,})", fontsize=10.5)
        ax.tick_params(axis="y", labelsize=8.5)
    for ax in axes.flat[len(groups):]:
        ax.axis("off")
    fig.suptitle(f"Top {n} skills within each occupation group (share of the group's postings)",
                 x=0.01, ha="left", fontsize=14, fontweight="bold")
    fig.tight_layout(rect=(0, 0.02, 1, 0.97))
    # most distinctive skill per group: highest lift among skills in >=5% of the group
    dist = (g[(g.share_jobs >= 0.05) & (g.position_group != "Other")]
            .sort_values("lift_vs_overall", ascending=False).groupby("position_group").head(1))
    ex = "; ".join(f"{pretty(r.position_group)} → {r.skill} ({pct(r.share_jobs)}, {r.lift_vs_overall:.1f}× overall)"
                   for r in dist.sort_values("lift_vs_overall", ascending=False).head(4).itertuples())
    rep.save(fig, "03_top15_by_group", f"Top {n} skills by occupation group",
             f"Soft skills top every group, but each group has a clear signature skill: {ex}.")


def fig_country(S, rep, n=25):
    c = S["by_country"]
    top = S["freq"].head(n).skill.tolist()
    m = c[c.skill.isin(top)].pivot(index="skill", columns="search_country", values="share_jobs").reindex(top).fillna(0)
    m = m[sorted(m.columns, key=lambda k: -c[c.search_country == k].n_jobs_in_group.iloc[0])]
    fig, ax = plt.subplots(figsize=(8.5, 10))
    im = ax.imshow(m.values, cmap=SEQ, aspect="auto", vmin=0)
    ax.set_xticks(range(m.shape[1]), m.columns)
    ax.set_yticks(range(len(top)), top)
    ax.xaxis.tick_top()
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    for i in range(m.shape[0]):
        for j in range(m.shape[1]):
            v = m.values[i, j]
            ax.text(j, i, pct(v, 0), ha="center", va="center", fontsize=8.5,
                    color="white" if v > 0.6 * m.values.max() else INK)
    ax.set_title(f"Share of postings mentioning each skill, by country (top {n} skills)", pad=28)
    fig.colorbar(im, ax=ax, shrink=0.5, format=lambda v, _: pct(v, 0), label="share of postings")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    spread = (m.max(axis=1) - m.min(axis=1)).sort_values(ascending=False)
    s0 = spread.index[0]
    rep.save(fig, "04_country_differences", "Country differences",
             f"The ranking is broadly stable across countries; the widest gap is {s0}: "
             f"{pct(m.loc[s0].max())} in {m.loc[s0].idxmax()} vs {pct(m.loc[s0].min())} in {m.loc[s0].idxmin()}. "
             f"Second is {spread.index[1]} ({pct(m.loc[spread.index[1]].max())} in {m.loc[spread.index[1]].idxmax()} "
             f"vs {pct(m.loc[spread.index[1]].min())} in {m.loc[spread.index[1]].idxmin()}).",
             caption=CAPTION + (" US rows in the pilot cover only titles early in the alphabet (see report caveats)."
                                if S["partial"] else ""))


def fig_cooccurrence(S, rep, n=50):
    co = S["co"]
    top = S["freq"].head(n).skill.tolist()
    d = co[co.skill_a.isin(top) & co.skill_b.isin(top)]
    m = pd.DataFrame(1.0, index=top, columns=top)
    for r in d.itertuples():
        m.loc[r.skill_a, r.skill_b] = m.loc[r.skill_b, r.skill_a] = r.lift
    # order by hierarchical clustering on log-lift so related skills sit together
    from scipy.cluster.hierarchy import leaves_list, linkage
    lg = np.log2(m.clip(lower=0.05).values)
    np.fill_diagonal(lg, 0)
    order = leaves_list(linkage(lg, "average"))
    lg = lg[np.ix_(order, order)]
    names = [top[i] for i in order]
    np.fill_diagonal(lg, np.nan)
    fig, ax = plt.subplots(figsize=(14, 13))
    im = ax.imshow(lg, cmap=DIV, norm=TwoSlopeNorm(0, vmin=-2.5, vmax=2.5))
    ax.set_xticks(range(n), names, rotation=90, fontsize=8)
    ax.set_yticks(range(n), names, fontsize=8)
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    cb = fig.colorbar(im, ax=ax, shrink=0.6, ticks=[-2, -1, 0, 1, 2])
    cb.ax.set_yticklabels(["¼×", "½×", "1× (independent)", "2×", "4×"])
    cb.set_label("lift = observed co-occurrence ÷ expected if independent")
    ax.set_title(f"Skill co-occurrence lift among the top {n} skills (clustered order)")
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    strong = d[d.n_co >= 500].sort_values("lift", ascending=False).head(3)
    ex = "; ".join(f"{r.skill_a} + {r.skill_b} ({r.lift:.1f}×, {r.n_co:,} postings)" for r in strong.itertuples())
    rep.save(fig, "05_cooccurrence_top50", f"Skill co-occurrence (top {n})",
             f"Skills form occupational bundles rather than mixing freely; the strongest pairs among the top {n} are {ex}.")


def fig_edu_yoe(S, ov, rep):
    e, yo = S["edu"], S["yoe"]
    stated = e[e.edu_required != "not_stated"]
    tot = stated.groupby("edu_required").n_jobs.sum().reindex(EDU_ORDER).fillna(0)
    fig, axes = plt.subplots(1, 3, figsize=(18, 6), gridspec_kw={"width_ratios": [0.9, 1.5, 1.1]})
    hbar(axes[0], [EDU_LABEL[k] for k in tot.index], (tot / tot.sum()).to_numpy(), xlabel="share of postings stating a degree")
    axes[0].set_title(f"Required education (n={int(tot.sum()):,} stating one)")
    # per group: share of stated postings requiring bachelor or higher
    g = stated.assign(ba=stated.edu_required.isin(["bachelor", "master", "phd", "professional_doctorate"]))
    gg = g.groupby("position_group").apply(lambda d: pd.Series({
        "share": (d.n_jobs * d.ba).sum() / d.n_jobs.sum(), "n": d.n_jobs.sum()}), include_groups=False).sort_values("share", ascending=False)
    hbar(axes[1], [f"{pretty(k)} (n={int(n):,})" for k, n in zip(gg.index, gg.n)], gg.share.to_numpy(),
         xlabel="share requiring bachelor or higher, among postings stating a degree")
    axes[1].set_title("Bachelor+ requirement by occupation group")
    y = yo.dropna(subset=["yoe_min_overall"])
    yy = y.assign(b=y.yoe_min_overall.clip(upper=10).round().astype(int)).groupby("b").n_jobs.sum()
    yy = yy.reindex(range(0, 11)).fillna(0)
    ax = axes[2]
    ax.bar(yy.index, yy / yy.sum(), color=BLUE, width=0.72, zorder=2)
    ax.yaxis.grid(True, color=GRID, lw=0.6, zorder=0)
    ax.set_xticks(range(0, 11), [str(i) for i in range(10)] + ["10+"])
    ax.yaxis.set_major_formatter(lambda v, _: pct(v, 0))
    ax.set_xlabel("minimum years of experience")
    ax.set_title(f"Required experience (n={int(yy.sum()):,} stating one)")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    ba = tot[["bachelor", "master", "phd", "professional_doctorate"]].sum() / tot.sum()
    le3 = yy.loc[:3].sum() / yy.sum()
    rep.save(fig, "06_education_experience", "Education and experience requirements",
             f"Among the {pct(ov['share_jobs_edu_stated'])} of postings that state a degree, {pct(ba)} ask for a bachelor's or higher "
             f"(bachelor alone {pct(tot['bachelor'] / tot.sum())}); highest in {pretty(gg.index[0])} ({pct(gg.share.iloc[0])}), "
             f"lowest in {pretty(gg.index[-1])} ({pct(gg.share.iloc[-1])}). Among the {pct(ov['share_jobs_yoe_stated'])} stating experience, "
             f"the median minimum is {ov['yoe_median_when_stated']:.0f} years and {pct(le3)} ask for 3 years or fewer.",
             caption="Quality: edu_required accuracy≈0.86, yoe accuracy≈0.84 on 50 unseen postings; errors are mostly "
                     "missed values, so 'not stated' is over-counted and shares are computed among postings with a value.")


def fig_certs(S, rep, n=20):
    c = S["cert"].head(n)
    fig, ax = plt.subplots(figsize=(9, 7))
    hbar(ax, c.cert, c.share_jobs.to_numpy(), fmt=lambda v, d=2: f"{100 * v:.{d}f}%")
    ax.set_title(f"Top {n} certificates / licences by share of postings")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    rep.save(fig, "07_top20_certs", f"Top {n} certificates",
             f"{c.cert[0]} is by far the most requested credential ({pct(c.share_jobs[0])} of postings), followed by "
             f"{c.cert[1]} ({pct(c.share_jobs[1])}) and {c.cert[2]} ({pct(c.share_jobs[2])}); "
             f"healthcare credentials account for {int(c.head(10).cert.isin(['RN', 'CPR', 'BLS', 'NP', 'ACLS', 'PALS', 'LPN', 'CNA', 'Board Certification', 'PA']).sum())} of the top 10.",
             caption="Quality: per-posting certificate sets are unreliable (exact-set accuracy 0.56); only single-certificate "
                     "occurrence rates are shown. Counts include required and preferred mentions.")


def fig_soft_hard(S, rep):
    s = S["soft"]
    allrow = s[s.position_group == "ALL"].iloc[0]
    d = s[s.position_group != "ALL"].sort_values("soft_share_of_mentions", ascending=False)
    fig, ax = plt.subplots(figsize=(10, 6))
    y = np.arange(len(d))[::-1]
    soft = d.soft_share_of_mentions.to_numpy()
    ax.barh(y, soft, color=BLUE, height=0.68, label="soft skills", zorder=2)
    ax.barh(y, 1 - soft, left=soft, color=ORANGE, height=0.68, label="hard skills & tools", zorder=2,
            edgecolor=SURFACE, linewidth=1.5)
    ax.set_yticks(y, [pretty(v) for v in d.position_group])
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    for yi, v in zip(y, soft):
        ax.text(v - 0.01, yi, pct(v, 0), va="center", ha="right", color="white", fontsize=9, fontweight="bold")
    ax.axvline(allrow.soft_share_of_mentions, color=INK, lw=1, ls=(0, (3, 3)), zorder=3)
    ax.text(allrow.soft_share_of_mentions, len(d) - 0.35, f" all groups {pct(allrow.soft_share_of_mentions, 0)}",
            fontsize=8.5, color=INK, va="bottom")
    ax.set_xlim(0, 1)
    ax.xaxis.set_major_formatter(lambda v, _: pct(v, 0))
    ax.set_xlabel("share of specific skill mentions")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=2, frameon=False)
    ax.set_title("Soft vs hard skill mix by occupation group")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    rep.save(fig, "08_soft_vs_hard", "Soft vs hard skills",
             f"Soft skills are {pct(allrow.soft_share_of_mentions)} of specific skill mentions overall and appear in "
             f"{pct(allrow.share_jobs_any_soft)} of postings with skills; the mix ranges from {pct(d.soft_share_of_mentions.iloc[0])} "
             f"soft in {pretty(d.position_group.iloc[0])} to {pct(d.soft_share_of_mentions.iloc[-1])} in {pretty(d.position_group.iloc[-1])}.")


def load(summary_dir: Path) -> tuple[dict, dict]:
    r = lambda n: pd.read_csv(summary_dir / n)  # noqa: E731
    co = sorted(summary_dir.glob("skill_cooccurrence_top*.csv"))[0]
    S = {"jobs_by_dim": r("jobs_by_dim.csv"), "freq": r("skill_freq_overall.csv"),
         "by_group": r("skill_freq_by_position_group.csv"), "by_country": r("skill_freq_by_search_country.csv"),
         "co": pd.read_csv(co), "edu": r("edu_dist.csv"), "yoe": r("yoe_dist.csv"),
         "cert": r("cert_occurrence.csv"), "soft": r("soft_hard_by_position_group.csv")}
    ov = json.loads((summary_dir / "overview.json").read_text())
    S["partial"] = is_partial(ov)
    return S, ov


def is_partial(ov: dict) -> bool:
    """True when the summaries were built from a slice of the run's chunk files (the pilot)."""
    return any("chunk" in Path(p).name for p in ov["inputs"]["jobs"])


def caveats(ov: dict) -> str:
    c = ov["by_country"]
    n = ov["n_postings_dedup"]
    mix = ", ".join(f"{k} {pct(v / n, 0)}" for k, v in c.items())
    return (
        "## Caveats\n\n"
        f"- **Sample composition.** Inputs: `{ov['inputs']['jobs'][0]}` … ({len(ov['inputs']['jobs'])} file(s)). "
        f"Country mix here: {mix}. " + (
            "The full run processes postings in `job_link` order, so a partial slice is not a random "
            "sample: non-US postings come first, and US postings arrive alphabetically by title slug. In the 300k pilot slice, "
            "Australia, Canada and the UK are essentially complete, but the US covers only titles from 'a' to about 'band', "
            "and the US is ~32% of the slice versus ~85% of the full corpus. Treat pilot US and overall figures as provisional; "
            "the full-corpus version is built with `--preset full`.\n" if is_partial(ov) else
            "These are all postings of the full run. They come from LinkedIn searches in four English-speaking countries in "
            "early 2024 and are not a random sample of the labour market.\n") +
        "- **Skills.** Precision≈0.66, recall≈0.58 on 50 unseen postings: good for rankings and group comparisons, "
        "not for exact per-posting lists. The high-confidence subset (both `job_skills` and the description agree) has precision≈0.93 "
        "but lower coverage.\n"
        "- **Generic labels** (`is_generic`, `(unspecified)`) such as Management, Training, Leadership, Sales are excluded by default.\n"
        "- **Education / experience** are accurate when present (≈0.86 / ≈0.84) but often missed, so shares are among postings that state a value.\n"
        "- **Certificates**: only single-certificate occurrence rates; required and preferred are mixed.\n"
        "- **Dedup**: one posting per `dup_group_id`.\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--preset", choices=sorted(PRESETS), default="pilot", help="sets the three defaults below")
    ap.add_argument("--summary-dir", type=Path)
    ap.add_argument("--figures-dir", type=Path)
    ap.add_argument("--report", type=Path, help="default: outputs/eda_report.md (pilot) / _full.md (full)")
    args = ap.parse_args(argv)
    args.summary_dir = args.summary_dir or PRESETS[args.preset]["summary_dir"]
    args.figures_dir = args.figures_dir or PRESETS[args.preset]["figures_dir"]
    args.report = args.report or ROOT / "outputs" / ("eda_report.md" if args.preset == "pilot" else f"eda_report_{args.preset}.md")
    S, ov = load(args.summary_dir)
    rep = Report(args.figures_dir, args.report)
    fig_overview(S, ov, rep)
    fig_top_skills(S, rep)
    fig_by_group(S, rep)
    fig_country(S, rep)
    fig_cooccurrence(S, rep)
    fig_edu_yoe(S, ov, rep)
    fig_certs(S, rep)
    fig_soft_hard(S, rep)
    head = (f"# EDA report — LinkedIn skill demand\n\nGenerated {ov['generated_at_utc']} from `{args.summary_dir.name}` summaries: "
            f"{ov['n_postings_dedup']:,} deduplicated postings ({ov['n_postings_raw']:,} raw), "
            f"{ov['n_distinct_skills_specific']} specific skills.\n\n> {CAPTION}\n\n")
    args.report.write_text(head + "\n".join(rep.sections) + "\n" + caveats(ov))
    print("report →", args.report)


if __name__ == "__main__":
    main()
