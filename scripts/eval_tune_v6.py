#!/usr/bin/env python3
"""Tune-set evaluation against Claude gold labels (round 6).

Hard rule: only split=tune (150 jobs). Never read holdout labels for scoring.

Usage:
  python scripts/eval_tune_v6.py                  # v5 outputs + embedded review preds
  python scripts/eval_tune_v6.py --suffix v6      # scored against cleaned/*_v6_*
  python scripts/eval_tune_v6.py --from-review    # precision from review file itself (v5 baseline)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CLEANED = ROOT / "cleaned"
sys.path.insert(0, str(ROOT))

from extraction_resources import CERT_DICT, SKILL_DICT  # noqa: E402

SKILLS_CLAUDE = CLEANED / "review_template_skills_tune_v5_claude.csv"
GOLD_CLAUDE = CLEANED / "gold_annotation_template_v5_claude.csv"
QUAL_CLAUDE = CLEANED / "review_template_qualifications_tune_v5_claude.csv"
VAL_SAMPLE = CLEANED / "validation_sample_v5.csv"

# Near-synonym pairs for lenient recall (from llm_labeling_v5_notes.md)
NEAR_SYNONYMS = {
    "people management": {"team management"},
    "team management": {"people management"},
    "workplace / osha safety": {"safety (unspecified)", "osha safety", "safety"},
    "safety (unspecified)": {"workplace / osha safety", "osha safety"},
    "osha safety": {"workplace / osha safety", "safety (unspecified)"},
    "safety": {"workplace / osha safety"},
}


def _tune_links() -> set[str]:
    val = pd.read_csv(VAL_SAMPLE)
    return set(val.loc[val["split"] == "tune", "job_link"])


def _norm_edu(x) -> str | None:
    if pd.isna(x):
        return None
    s = str(x).strip().lower()
    if s in {"", "none", "nan"}:
        return None
    return s


def _norm_yoe(x) -> float | None:
    if pd.isna(x) or str(x).strip() == "" or str(x).strip().lower() == "nan":
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        m = re.search(r"(\d+(?:\.\d+)?)", str(x))
        return float(m.group(1)) if m else None


def _yoe_eq(a, b) -> bool:
    if a is None and b is None:
        return True
    if a in (None, 0.0) and b in (None, 0.0):
        return True
    return a == b


def _parse_certs(x) -> list[str]:
    if pd.isna(x) or not str(x).strip():
        return []
    return [p.strip() for p in re.split(r"\s*;\s*|\s*\|\s*", str(x)) if p.strip()]


_CERT_ALIAS = {}
for _k, _als in CERT_DICT.items():
    _CERT_ALIAS[_k.lower()] = _k.lower()
    for _a in _als:
        _CERT_ALIAS[_a.lower()] = _k.lower()


def _certs_dict_names(items: list[str]) -> set[str]:
    out = set()
    for it in items:
        key = it.lower()
        if key in _CERT_ALIAS:
            out.add(_CERT_ALIAS[key])
    return out


def _certs_all_names(items: list[str]) -> set[str]:
    out = set()
    for it in items:
        key = it.lower()
        out.add(_CERT_ALIAS.get(key, key))
    return out


def skill_precision(review: pd.DataFrame, preds: pd.DataFrame | None) -> dict:
    """Precision from Claude human_correct labels.

    If preds is None, use skill_predicted rows in the review file (v5 baseline).
    Else align current predictions to labels on (job_link, skill).
    """
    labels = review.copy()
    labels["hc_raw"] = labels["human_correct"].astype(str)
    judged = labels[labels["hc_raw"].isin(["0", "1"])].copy()
    judged["hc"] = judged["hc_raw"].astype(int)
    judged["skill_key"] = judged["skill_predicted"].astype(str)

    if preds is None:
        scored = judged
        unlabeled_n = 0
    else:
        p = preds.copy()
        skill_col = "skill_refined" if "skill_refined" in p.columns else "skill_predicted"
        p["skill_key"] = p[skill_col].astype(str)
        # one label per (job, skill) — if duplicate review rows, prefer any 0 (stricter)
        lab = (
            judged.groupby(["job_link", "skill_key"], as_index=False)
            .agg(hc=("hc", "min"), error_type=("error_type", "first"),
                 evidence_status=("evidence_status", "first"), sources=("sources", "first"),
                 job_family_pred=("job_family_pred", "first"))
        )
        merged = p.merge(lab, on=["job_link", "skill_key"], how="left")
        scored = merged[merged["hc"].notna()].copy()
        unlabeled_n = int(merged["hc"].isna().sum())

    n = len(scored)
    tp = int(scored["hc"].sum())
    out = {
        "precision_overall": tp / n if n else None,
        "tp": tp,
        "n_judged": n,
        "unlabeled_preds": unlabeled_n,
    }
    for col in ("evidence_status", "sources"):
        if col not in scored.columns:
            continue
        by = {}
        for k, g in scored.groupby(col):
            by[str(k)] = {
                "precision": float(g["hc"].mean()) if len(g) else None,
                "tp": int(g["hc"].sum()),
                "n": int(len(g)),
            }
        out[f"by_{col}"] = by

    # error type distribution on false positives
    fps = scored[scored["hc"] == 0]
    if "error_type" in fps.columns:
        out["error_type_counts"] = Counter(
            str(x) for x in fps["error_type"].fillna("unknown")
        )

    # worst 15 skills (≥5 rows)
    worst = []
    for skill, g in scored.groupby("skill_key"):
        if len(g) < 5:
            continue
        worst.append((skill, float(g["hc"].mean()), int(g["hc"].sum()), int(len(g))))
    worst.sort(key=lambda x: (x[1], x[3]))
    out["worst_15_skills"] = [
        {"skill": s, "precision": p, "tp": t, "n": n_} for s, p, t, n_ in worst[:15]
    ]

    # by job_family_pred
    if "job_family_pred" in scored.columns:
        fam = {}
        for k, g in scored.groupby("job_family_pred"):
            # job-level? notes use row-level by family of the job
            fam[str(k)] = {
                "precision": float(g["hc"].mean()),
                "n": int(len(g)),
            }
        out["by_job_family_pred"] = fam
    return out


def skill_recall(gold: pd.DataFrame, preds: pd.DataFrame) -> dict:
    fr = gold[(gold["split"] == "tune") & (gold["full_recall"] == True)].copy()
    skill_col = "skill_refined" if "skill_refined" in preds.columns else "skill_predicted"
    pred_by = {
        link: set(g[skill_col].dropna().astype(str).str.lower())
        for link, g in preds.groupby("job_link")
    }
    hit_s = hit_l = tot = 0
    miss = Counter()
    oov_tot = oov_hit = 0
    for _, r in fr.iterrows():
        golds = [x.strip() for x in str(r.get("gold_skills_all") or "").split(";") if x.strip()]
        preds_set = pred_by.get(r["job_link"], set())
        for s in golds:
            if s.startswith("OOV:"):
                oov_tot += 1
                # OOV never matches vocab preds
                continue
            tot += 1
            sl = s.lower()
            ok_s = sl in preds_set
            ok_l = ok_s or bool(NEAR_SYNONYMS.get(sl, set()) & preds_set)
            if ok_s:
                hit_s += 1
            else:
                miss[s] += 1
            if ok_l:
                hit_l += 1
    return {
        "recall_strict": hit_s / tot if tot else None,
        "recall_lenient": hit_l / tot if tot else None,
        "hit_strict": hit_s,
        "hit_lenient": hit_l,
        "n_invocab_gold": tot,
        "n_oov_gold": oov_tot,
        "most_missed_15": [{"skill": s, "n": n} for s, n in miss.most_common(15)],
    }


def job_family_accuracy(gold: pd.DataFrame, features: pd.DataFrame | None) -> dict:
    tune = gold[gold["split"] == "tune"].copy()
    if features is not None and "job_family" in features.columns:
        fmap = dict(zip(features["job_link"], features["job_family"]))
        tune["job_family_pred_eval"] = tune["job_link"].map(fmap).fillna(tune["job_family_pred"])
    else:
        tune["job_family_pred_eval"] = tune["job_family_pred"]

    strict = (tune["job_family_pred_eval"] == tune["job_family_gold"]).sum()
    # lenient: accept alt: X in annotator_notes
    lenient = 0
    for _, r in tune.iterrows():
        pred = r["job_family_pred_eval"]
        gold_f = r["job_family_gold"]
        if pred == gold_f:
            lenient += 1
            continue
        notes = str(r.get("annotator_notes") or "")
        m = re.search(r"\(alt:\s*([^)]+)\)", notes, re.I)
        if m and pred == m.group(1).strip():
            lenient += 1
    n = len(tune)
    # confusion
    conf = Counter()
    for _, r in tune.iterrows():
        if r["job_family_pred_eval"] != r["job_family_gold"]:
            conf[(r["job_family_pred_eval"], r["job_family_gold"])] += 1
    return {
        "accuracy_strict": strict / n if n else None,
        "accuracy_lenient": lenient / n if n else None,
        "correct_strict": int(strict),
        "n": n,
        "other_pred_n": int((tune["job_family_pred_eval"] == "Other").sum()),
        "mgmt_pred_n": int((tune["job_family_pred_eval"] == "Management General").sum()),
        "top_confusions": [
            {"pred": a, "gold": b, "n": c} for (a, b), c in conf.most_common(10)
        ],
    }


def quals_accuracy(qual_gold: pd.DataFrame, features: pd.DataFrame | None) -> dict:
    q = qual_gold.copy()
    if features is not None:
        cols = [
            "job_link", "edu_required", "edu_preferred",
            "yoe_min_overall", "yoe_max_overall", "certifications_pipe",
        ]
        # optional v6 columns
        for c in ("yoe_min_required", "yoe_min_preferred"):
            if c in features.columns:
                cols.append(c)
        feat = features[[c for c in cols if c in features.columns]].drop_duplicates("job_link")
        q = q.drop(
            columns=[c for c in [
                "edu_required_pred", "edu_preferred_pred",
                "yoe_min_overall_pred", "yoe_max_overall_pred", "certs_pred",
            ] if c in q.columns],
            errors="ignore",
        ).merge(feat, on="job_link", how="left")
        q = q.rename(columns={
            "edu_required": "edu_required_pred",
            "edu_preferred": "edu_preferred_pred",
            "yoe_min_overall": "yoe_min_overall_pred",
            "yoe_max_overall": "yoe_max_overall_pred",
            "certifications_pipe": "certs_pred",
        })

    n = len(q)
    edu_ok = sum(
        _norm_edu(r.edu_required_pred) == _norm_edu(r.edu_required_gold)
        for _, r in q.iterrows()
    )
    pref_ok = sum(
        _norm_edu(r.edu_preferred_pred) == _norm_edu(r.edu_preferred_gold)
        for _, r in q.iterrows()
    )
    yoe_ok = sum(
        _yoe_eq(_norm_yoe(r.yoe_min_overall_pred), _norm_yoe(r.yoe_overall_gold))
        for _, r in q.iterrows()
    )
    cert_all = cert_in = 0
    for _, r in q.iterrows():
        p_all = _certs_all_names(_parse_certs(r.certs_pred))
        g_all = _certs_all_names(_parse_certs(r.certs_required_gold))
        if p_all == g_all:
            cert_all += 1
        if _certs_dict_names(_parse_certs(r.certs_pred)) == _certs_dict_names(
            _parse_certs(r.certs_required_gold)
        ):
            cert_in += 1
    return {
        "edu_required_acc": edu_ok / n,
        "edu_preferred_acc": pref_ok / n,
        "yoe_overall_acc": yoe_ok / n,
        "certs_required_in_dict_acc": cert_in / n,
        "certs_required_all_acc": cert_all / n,
        "n": n,
        "edu_correct": edu_ok,
        "yoe_correct": yoe_ok,
        "certs_in_dict_correct": cert_in,
        "certs_all_correct": cert_all,
    }


def load_preds(suffix: str, tune: set[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    skills = pd.read_csv(CLEANED / f"job_skill_refined_{suffix}_sample5000.csv")
    feats = pd.read_csv(CLEANED / f"job_features_{suffix}_sample5000.csv")
    skills = skills[skills["job_link"].isin(tune)].copy()
    feats = feats[feats["job_link"].isin(tune)].copy()
    return skills, feats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suffix", default="v5", help="pipeline output suffix (v5/v6)")
    ap.add_argument(
        "--from-review",
        action="store_true",
        help="score precision using predictions embedded in the Claude review file",
    )
    ap.add_argument("--json-out", default="", help="optional path for JSON dump")
    args = ap.parse_args()

    tune = _tune_links()
    review = pd.read_csv(SKILLS_CLAUDE)
    assert not set(review["job_link"]) - tune, "skills review contains non-tune jobs"
    gold = pd.read_csv(GOLD_CLAUDE)
    # never use holdout gold for scoring beyond confirming family blanks
    hold = gold[gold["split"] == "holdout"]
    hold_filled = hold["job_family_gold"].dropna().astype(str).str.strip()
    hold_filled = hold_filled[hold_filled != ""]
    if len(hold_filled):
        print(f"WARNING: {len(hold_filled)} holdout rows have job_family_gold — ignored for scoring")

    qual = pd.read_csv(QUAL_CLAUDE)
    assert set(qual["job_link"]) <= tune

    if args.from_review:
        preds = None
        feats = None
        # for recall/family still need some pred source from review / gold pred cols
        preds_for_recall = review.rename(columns={"skill_predicted": "skill_refined"})[
            ["job_link", "skill_refined"]
        ]
        feats_for_family = None
    else:
        preds, feats = load_preds(args.suffix, tune)
        preds_for_recall = preds
        feats_for_family = feats

    prec = skill_precision(review, preds)
    rec = skill_recall(gold, preds_for_recall)
    fam = job_family_accuracy(gold, feats_for_family)
    # quals: from-review uses embedded preds; else current features
    if args.from_review:
        quals = quals_accuracy(qual, None)
    else:
        quals = quals_accuracy(qual, feats)

    report = {
        "suffix": args.suffix if not args.from_review else "review_embedded_v5",
        "skill_precision": prec,
        "skill_recall": rec,
        "job_family": fam,
        "qualifications": quals,
    }

    def pct(x):
        return f"{x:.3f}" if x is not None else "n/a"

    print("=== tune eval ===")
    print(f"source: {report['suffix']}")
    print(f"skill precision          {pct(prec['precision_overall'])}  ({prec['tp']}/{prec['n_judged']})"
          + (f"  unlabeled_preds={prec['unlabeled_preds']}" if prec.get('unlabeled_preds') else ""))
    for k, v in (prec.get("by_sources") or {}).items():
        print(f"  sources={k:20s} {pct(v['precision'])}  ({v['tp']}/{v['n']})")
    print(f"skill recall strict      {pct(rec['recall_strict'])}  ({rec['hit_strict']}/{rec['n_invocab_gold']})")
    print(f"skill recall lenient     {pct(rec['recall_lenient'])}  ({rec['hit_lenient']}/{rec['n_invocab_gold']})")
    print(f"job_family strict        {pct(fam['accuracy_strict'])}  ({fam['correct_strict']}/{fam['n']})")
    print(f"edu_required             {pct(quals['edu_required_acc'])}  ({quals['edu_correct']}/{quals['n']})")
    print(f"yoe_overall              {pct(quals['yoe_overall_acc'])}  ({quals['yoe_correct']}/{quals['n']})")
    print(f"certs_required (in-dict) {pct(quals['certs_required_in_dict_acc'])}  ({quals['certs_in_dict_correct']}/{quals['n']})")
    print(f"certs_required (all)     {pct(quals['certs_required_all_acc'])}  ({quals['certs_all_correct']}/{quals['n']})")

    print("\n--- error types (FP) ---")
    for k, v in (prec.get("error_type_counts") or Counter()).most_common():
        print(f"  {k}: {v}")
    print("\n--- worst 15 skills ---")
    for row in prec.get("worst_15_skills") or []:
        print(f"  {row['skill']}: {row['precision']:.3f} ({row['tp']}/{row['n']})")
    print("\n--- most missed 15 (recall) ---")
    for row in rec.get("most_missed_15") or []:
        print(f"  {row['skill']}: {row['n']}")
    print("\n--- top family confusions ---")
    for row in fam.get("top_confusions") or []:
        print(f"  {row['pred']} → {row['gold']}: {row['n']}")

    out_path = Path(args.json_out) if args.json_out else CLEANED / f"eval_tune_{report['suffix']}.json"
    # Counter not JSON-serializable
    dump = json.loads(json.dumps(report, default=lambda o: dict(o) if isinstance(o, Counter) else str(o)))
    out_path.write_text(json.dumps(dump, indent=2))
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
