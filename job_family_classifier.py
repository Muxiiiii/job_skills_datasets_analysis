"""Round8 job_family: TF-IDF + LogisticRegression (no more tune-overfit regex).

Raw LinkedIn dump has no job_function / industry field — use title (+ optional
summary head) trained on tune-150 Claude gold labels.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import Pipeline

CLEANED = Path(__file__).resolve().parent / "cleaned"
GOLD_PATH = CLEANED / "gold_annotation_template_v5_claude.csv"
MODEL_PATH = CLEANED / "job_family_tfidf_lr_v8.joblib"
META_PATH = CLEANED / "job_family_tfidf_lr_v8_meta.json"
PARQUET = CLEANED / "jobs_combined.parquet"

# Coarse 9-bucket fallback if fine-grained CV < 0.70
COARSE_MAP = {
    "Nursing & Clinical": "Healthcare",
    "Physician & PA": "Healthcare",
    "Allied Health": "Healthcare",
    "Imaging & Radiology": "Healthcare",
    "Behavioral Health": "Healthcare",
    "Pharmacy": "Healthcare",
    "Lab & Science": "Healthcare",
    "Veterinary": "Healthcare",
    "Personal Care": "Healthcare",
    "Software & IT Engineering": "Tech & Data",
    "IT & Cybersecurity": "Tech & Data",
    "Data & Analytics": "Tech & Data",
    "Business Analyst": "Tech & Data",
    "Engineering (Non-software)": "Engineering & Trades",
    "Construction & Trades": "Engineering & Trades",
    "Inspection & QA": "Engineering & Trades",
    "Retail Ops": "Customer-facing",
    "Hospitality & Food": "Customer-facing",
    "Sales": "Customer-facing",
    "Customer Support": "Customer-facing",
    "Finance & Accounting": "Business Ops",
    "HR": "Business Ops",
    "Supply Chain & Ops": "Business Ops",
    "Project / Product Mgmt": "Business Ops",
    "Management General": "Business Ops",
    "Administrative": "Business Ops",
    "Marketing": "Business Ops",
    "Legal": "Professional Services",
    "Education": "Professional Services",
    "Risk & Compliance": "Professional Services",
    "Protective Services": "Professional Services",
    "Other": "Other",
}


def _summary_head(text: Optional[str], n_words: int = 300) -> str:
    if not isinstance(text, str) or not text.strip():
        return ""
    words = re.findall(r"\S+", text)
    return " ".join(words[:n_words])


def _load_tune_xy(*, coarse: bool = False):
    gold = pd.read_csv(GOLD_PATH)
    tune = gold[gold["split"] == "tune"].copy()
    tune = tune.dropna(subset=["job_family_gold", "job_link"])
    titles = tune["job_title"].fillna("").astype(str) if "job_title" in tune.columns else pd.Series([""] * len(tune))
    if "summary_full" in tune.columns:
        summ = tune["summary_full"]
    elif "job_summary" in tune.columns:
        summ = tune["job_summary"]
    else:
        import duckdb
        links = tune["job_link"].tolist()
        df = duckdb.connect().execute(
            "SELECT job_link, job_summary FROM read_parquet(?) WHERE job_link = ANY(?)",
            [str(PARQUET), links],
        ).df()
        tune = tune.merge(df, on="job_link", how="left")
        summ = tune["job_summary"]
    heads = summ.fillna("").map(lambda s: _summary_head(s, 300))
    X = [(f"{t} {h}").strip() or "unknown" for t, h in zip(titles.tolist(), heads.tolist())]
    y = tune["job_family_gold"].astype(str).tolist()
    if coarse:
        y = [COARSE_MAP.get(lab, "Other") for lab in y]
    return X, y, tune["job_link"].tolist()


def _make_pipeline() -> Pipeline:
    return Pipeline([
        ("tfidf", TfidfVectorizer(
            ngram_range=(1, 2),
            min_df=1,
            max_features=8000,
            sublinear_tf=True,
            strip_accents="unicode",
        )),
        ("clf", LogisticRegression(
            max_iter=2000,
            class_weight="balanced",
            solver="lbfgs",
            C=2.0,
        )),
    ])


def _cv_report(X, y, *, n_splits: int = 5) -> dict:
    """Stratified CV; drop classes with < n_splits support for foldability."""
    from collections import Counter
    counts = Counter(y)
    keep = {lab for lab, n in counts.items() if n >= n_splits}
    idx = [i for i, lab in enumerate(y) if lab in keep]
    if len(idx) < n_splits * 2:
        return {"accuracy": 0.0, "n_used": 0, "n_dropped_classes": len(counts) - len(keep),
                "note": "too few samples for stratified CV"}
    Xk = [X[i] for i in idx]
    yk = [y[i] for i in idx]
    pipe = _make_pipeline()
    cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
    preds = cross_val_predict(pipe, Xk, yk, cv=cv)
    acc = float(np.mean(np.array(preds) == np.array(yk)))
    # top confusions
    from collections import Counter as C
    conf = C()
    for a, b in zip(yk, preds):
        if a != b:
            conf[(a, b)] += 1
    top5 = [{"gold": a, "pred": b, "n": n} for (a, b), n in conf.most_common(5)]
    return {
        "accuracy": acc,
        "n_used": len(yk),
        "n_classes_used": len(keep),
        "n_dropped_classes": len(counts) - len(keep),
        "top_confusions": top5,
    }


def train_and_save() -> dict:
    """Train fine-grained labels (gold taxonomy).

    Coarse 9-bucket CV is reported for transparency; we still ship the fine model
    because holdout/tune gold uses fine names (coarse preds would not be scorable).
    """
    X, y_fine, _ = _load_tune_xy(coarse=False)
    fine_cv = _cv_report(X, y_fine, n_splits=5)
    Xc, y_coarse, _ = _load_tune_xy(coarse=True)
    coarse_cv = _cv_report(Xc, y_coarse, n_splits=5)
    # Prefer fine whenever it is competitive; coarse only if clearly better AND we
    # remapped gold (we do not — keep fine for eval compatibility).
    label_space = "fine"
    y = y_fine
    cv = fine_cv
    pipe = _make_pipeline()
    pipe.fit(X, y)
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"pipeline": pipe, "label_space": label_space, "coarse_map": COARSE_MAP}, MODEL_PATH)
    meta = {
        "method": "tfidf_logistic_regression",
        "features": "job_title + first_300_words_of_summary",
        "train_n": len(X),
        "label_space": label_space,
        "fine_cv": fine_cv,
        "coarse_cv": coarse_cv,
        "selected_cv": cv,
        "linkedin_native_fields": None,
        "note": (
            "parquet has no job_function/industry. Fine 5-fold CV≈0.69 on classes with "
            "n≥5; coarse9 CV was lower. Ship fine labels to match gold taxonomy; "
            "title rules used only when classifier proba < min_proba."
        ),
    }
    # numpy / np.str_ → plain JSON
    def _clean(o):
        if isinstance(o, dict):
            return {k: _clean(v) for k, v in o.items()}
        if isinstance(o, list):
            return [_clean(v) for v in o]
        if isinstance(o, (np.floating, np.integer)):
            return o.item()
        if isinstance(o, np.str_):
            return str(o)
        return o
    meta = _clean(meta)
    META_PATH.write_text(json.dumps(meta, indent=2))
    return meta


_MODEL_CACHE = None


def load_model():
    """Load frozen model only — never train/overwrite (full-run / freeze safety)."""
    global _MODEL_CACHE
    if _MODEL_CACHE is not None:
        return _MODEL_CACHE
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Frozen job_family model not found: {MODEL_PATH}. "
            "Do not auto-train; restore the frozen joblib or run train_and_save() explicitly."
        )
    _MODEL_CACHE = joblib.load(MODEL_PATH)
    return _MODEL_CACHE


def predict_job_family(
    title: Optional[str],
    summary: Optional[str] = None,
    *,
    min_proba: float = 0.18,
) -> dict:
    """Return {job_family, job_family_rule, job_family_status, job_family_proba}."""
    from skill_refinement import assign_job_family_detailed as rules_detailed

    title = title if isinstance(title, str) else ""
    text = (title + " " + _summary_head(summary, 300)).strip()
    if not text:
        return rules_detailed(title)

    bundle = load_model()
    pipe = bundle["pipeline"]
    proba = pipe.predict_proba([text])[0]
    classes = list(pipe.named_steps["clf"].classes_)
    best_i = int(np.argmax(proba))
    pred = classes[best_i]
    p = float(proba[best_i])

    if p < min_proba:
        fb = rules_detailed(title)
        fb["job_family_proba"] = p
        fb["job_family_rule"] = f"rules_fallback_after_clf:{fb.get('job_family_rule')}"
        return fb

    return {
        "job_family": pred,
        "job_family_rule": f"tfidf_lr:{bundle.get('label_space', 'fine')}",
        "job_family_status": "matched",
        "job_family_proba": p,
    }


if __name__ == "__main__":
    meta = train_and_save()
    print(json.dumps(meta, indent=2))
