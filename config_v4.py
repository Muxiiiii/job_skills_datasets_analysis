"""v4 pipeline configuration — all input paths live here."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Raw LinkedIn dump (Kaggle asaniczka)
RAW_POSTINGS = ROOT / "linkedin_job_postings.csv"
RAW_SKILLS = ROOT / "job_skills.csv"
RAW_SUMMARY = ROOT / "job_summary.csv"

# Explicit named caches (full multi-country join)
CLEANED = ROOT / "cleaned"
JOBS_COMBINED = CLEANED / "jobs_combined.parquet"          # ALL countries
JOBS_COMBINED_US = CLEANED / "jobs_combined_us.parquet"    # EDA filter only — never for extraction body
ALIAS_CSV = ROOT / "skill_alias.csv"

# Sample / run controls
SAMPLE_N = 5_000
RANDOM_SEED = 42
# EDA default country filter (extraction always runs all countries present in the sample)
EDA_DEFAULT_COUNTRY = "United States"
# When True, sample only US jobs for the 5k development slice; False = stratified multi-country
SAMPLE_US_ONLY = False

TAG = "sample5000"
OUT_SUFFIX = "v4"

VALIDATION_N = 200
VALIDATION_TUNE = 150
VALIDATION_HOLDOUT = 50
VALIDATION_FULL_RECALL = 30
VALIDATION_SEED = 42
