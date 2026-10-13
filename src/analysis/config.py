"""Shared paths and input presets for the analysis layer.

Every script takes its inputs as CLI arguments; the presets here are only the
defaults. After the full run finishes, re-run with ``--preset full`` (or pass
``--jobs/--skills/--certs`` explicitly) — no code change needed.
"""

from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FULL_DIR = ROOT / "outputs" / "full_v8"
CHUNK_DIR = FULL_DIR / "chunks"

# Chunks that were complete when the pilot analysis was built (300k postings).
PILOT_CHUNKS = "0-5"

PRESETS = {
    "pilot": {
        "summary_dir": ROOT / "outputs" / "summary" / "pilot",
        "figures_dir": ROOT / "outputs" / "figures",
    },
    "full": {
        "jobs": [FULL_DIR / "jobs_v8.parquet"],
        "skills": [FULL_DIR / "job_skills_v8.parquet"],
        "certs": [FULL_DIR / "job_certs_v8.parquet"],
        "summary_dir": ROOT / "outputs" / "summary" / "full",
        "figures_dir": ROOT / "outputs" / "figures_full",
    },
}

# Quality numbers from cleaned/final_eval_v8.md (fresh 50 unseen postings).
QUALITY = {
    "skill_precision": 0.66,
    "skill_recall": 0.58,
    "skill_precision_high_conf": 0.93,
    "edu_required_acc": 0.86,
    "yoe_overall_acc": 0.84,
    "certs_exact_set_acc": 0.56,
    "job_family_pred_acc": 0.62,
}
QUALITY_NOTE = (
    "Skill extraction precision≈0.66 / recall≈0.58 on 50 unseen postings "
    "(two-source high-confidence subset: precision≈0.93). "
    "Use for rankings and group comparisons, not as per-posting skill lists."
)


def parse_chunks(spec: str) -> list[int]:
    """'0-5' or '0,2,4-6' -> sorted list of chunk indices."""
    out: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            out.update(range(int(a), int(b) + 1))
        else:
            out.add(int(part))
    return sorted(out)


def chunk_paths(kind: str, spec: str, chunk_dir: Path = CHUNK_DIR) -> list[Path]:
    return [chunk_dir / f"{kind}_chunk_{i:04d}.parquet" for i in parse_chunks(spec)]


def add_input_args(ap: argparse.ArgumentParser) -> None:
    ap.add_argument("--preset", choices=sorted(PRESETS), default="pilot")
    ap.add_argument("--chunks", default=PILOT_CHUNKS,
                    help="chunk indices for the pilot preset, e.g. 0-5")
    ap.add_argument("--chunk-dir", type=Path, default=CHUNK_DIR)
    ap.add_argument("--jobs", nargs="+", type=Path, help="jobs parquet file(s); overrides preset")
    ap.add_argument("--skills", nargs="+", type=Path, help="job-skill parquet file(s)")
    ap.add_argument("--certs", nargs="+", type=Path, help="job-cert parquet file(s)")
    ap.add_argument("--summary-dir", type=Path, help="where summary tables live")


def resolve_inputs(args: argparse.Namespace) -> dict:
    """Merge preset + explicit CLI paths into one dict of resolved paths."""
    preset = dict(PRESETS[args.preset])
    if args.preset == "pilot":
        for kind in ("jobs", "skills", "certs"):
            preset[kind] = chunk_paths(kind, args.chunks, args.chunk_dir)
    for kind in ("jobs", "skills", "certs"):
        if getattr(args, kind, None):
            preset[kind] = list(getattr(args, kind))
    if getattr(args, "summary_dir", None):
        preset["summary_dir"] = args.summary_dir
    for kind in ("jobs", "skills", "certs"):
        missing = [p for p in preset[kind] if not Path(p).exists()]
        if missing:
            raise SystemExit(f"missing {kind} input(s): {missing[:3]}")
    return preset


def sql_list(paths) -> str:
    """DuckDB list literal for read_parquet([...])."""
    return "[" + ", ".join("'" + str(p).replace("'", "''") + "'" for p in paths) + "]"
