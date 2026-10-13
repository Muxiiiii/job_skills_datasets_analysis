"""Map LinkedIn search_position → 12 reviewable analysis groups (full-run v8)."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
CONFIG_CSV = ROOT / "config" / "search_position_groups.csv"

# Ordered rules: first match wins. Human-readable groups for EDA.
_GROUP_RULES: list[tuple[str, re.Pattern]] = [
    ("Healthcare_Nursing", re.compile(
        r"(?i)\bnurse|\bnursing\b|\blpn\b|\bcna\b|\bmidwife\b|\banesthetist\b|"
        r"infection\s+control|nurse\s+practitioner|\bnurse-"
    )),
    ("Healthcare_Clinical", re.compile(
        r"(?i)\bphysician|\bdoctor\b|\bsurgeon\b|\bdermatolog|\banesthesiolog|"
        r"\bpsychiatr|\btherapist\b|\bpsycholog|\bcounselor\b|\bpharmacist\b|"
        r"\bdental\b|\bdentist\b|\bhygienist\b|\bsonograph|\bradiolog|"
        r"\btechnologist\b|\btechnician\b.*(?:med|lab|radio|nuclear|echo|ultra)|"
        r"\bparamedic\b|\bemt\b|\bvet(?:erinarian)?\b|\bcompanion\b|"
        r"family\s+practitioner|\boptometr|\bchiropract|\boccupational\s+ther|"
        r"physical\s+ther|\brespiratory\b|\bphlebotom|\bmedical\s+assist|"
        r"\bclinician\b|\bpatholog|\boncolog|\bcardiolog|\bneurolog"
    )),
    ("Education", re.compile(
        r"(?i)\beducation|\binstructor\b|\bteacher\b|\bprincipal\b|\bprofessor\b|"
        r"\btutor\b|\bschool\b|\bacademic\b|\bcurriculum\b|educational\s+program|"
        r"consultant\s+education"
    )),
    ("Tech_Engineering", re.compile(
        r"(?i)\bengineer|\bsoftware\b|\bdeveloper\b|\bprogrammer\b|\barchitect\b|"
        r"\bdevops\b|\bdata\s+(?:scientist|engineer|analyst)\b|\bcyber\b|"
        r"\bit\b|\bsystem(?:s)?\s+admin|\bnetwork\b|\bcloud\b|\bmachine\s+learning\b|"
        r"aeronautical|agricultural-research\s+engineer"
    )),
    ("Sales_Customer", re.compile(
        r"(?i)\bsales\b|\baccount\s+executive\b|\brepresentative\b|\brecycler\b|"
        r"customer\s+service|\bcashier\b|\bguide\b|\bextra\b|\bmodel\b|"
        r"circulation-sales|change\s+person|\brecruiter\b(?!\s+nurse)"
    )),
    ("Finance_Accounting", re.compile(
        r"(?i)\baccount(?:ant|ing)\b|\bfinanc|\bauditor\b|\bcontroller\b|"
        r"\beconomist\b|\bbookkeep|\btreasury\b|\btax\b|\bpayroll\b|"
        r"manager\s+benefits|check\s+cashier"
    )),
    ("Hospitality_Food", re.compile(
        r"(?i)\bchef\b|\bcook\b|\bbakery\b|\bbaker\b|\bwaiter\b|\bbartender\b|"
        r"\bhospitality\b|\bhotel\b|\brestaurant\b|\bfood\s+service\b|"
        r"\bcatering\b|\bbarista\b|\bserver\b|\bsteward\b"
    )),
    ("Skilled_Trades_Ops", re.compile(
        r"(?i)\bdriver\b|\binspector\b|\bassembler\b|\bmechanic\b|\belectrician\b|"
        r"\bplumber\b|\bweld(?:er|ing)\b|\bcarpenter\b|\bhvac\b|\boperator\b|"
        r"\bwarehouse\b|\blogistic|\bmanufactur|\bproduction\b|\bmaintenance\b|"
        r"\bconstruction\b|\blaborer\b|\btechnician\b|\bbridge\s+inspector\b|"
        r"car\s+inspector|special\s+effects"
    )),
    ("Management_HR_Admin", re.compile(
        r"(?i)\bmanager\b|\bdirector\b|\bsupervisor\b|\bcoordinator\b|"
        r"\brecruiter\b|\bhr\b|\bhuman\s+resource|\bclerk\b|\badmin|"
        r"\bexecutive\s+assistant\b|\boffice\b|\breception|\bsecretary\b|"
        r"manager\s+employment|director\s+social|director\s+nursing|"
        r"nurse\s+supervisor|bakery\s+supervisor|driver\s+supervisor"
    )),
    ("Legal_Compliance", re.compile(
        r"(?i)\blawyer\b|\battorney\b|\blegal\b|\bparalegal\b|\bcompliance\b|"
        r"\bcounsel\b|\bsolicitor\b|\bnotary\b"
    )),
    ("Science_Research", re.compile(
        r"(?i)\bbiologist\b|\bchemist\b|\bresearch(?:er)?\b|\bscientist\b|"
        r"\blaboratory\b|\blab\b|\bstatistician\b|\bepidemiolog"
    )),
    ("Creative_Media", re.compile(
        r"(?i)\bproducer\b|\bdesigner\b|\bwriter\b|\beditor\b|\bartist\b|"
        r"\bphotographer\b|\bvideo\b|\bmedia\b|\bmarketing\b|\bcontent\b|"
        r"special\s+effects\s+specialist|\bmodel\b"
    )),
]


def group_for_position(pos: str) -> str:
    if not isinstance(pos, str) or not pos.strip():
        return "Other"
    # Management patterns that embed nurse/driver etc. — check supervisor/manager of clinical last
    # Use ordered rules; more specific healthcare first already.
    for g, cre in _GROUP_RULES:
        if cre.search(pos):
            return g
    return "Other"


def build_mapping_csv(counts_csv: Path | None = None, out: Path = CONFIG_CSV) -> pd.DataFrame:
    """Build searchable mapping table for all observed search_position values."""
    if counts_csv is None:
        counts_csv = ROOT / "outputs" / "summary" / "search_position_all_counts.csv"
    df = pd.read_csv(counts_csv)
    df["position_group"] = df["search_position"].map(group_for_position)
    out.parent.mkdir(parents=True, exist_ok=True)
    df[["search_position", "position_group", "c"]].rename(columns={"c": "n_jobs"}).to_csv(out, index=False)
    return df


def load_group_map(path: Path = CONFIG_CSV) -> dict[str, str]:
    if not path.exists():
        build_mapping_csv(out=path)
    df = pd.read_csv(path)
    return dict(zip(df["search_position"].astype(str), df["position_group"].astype(str)))


if __name__ == "__main__":
    df = build_mapping_csv()
    print(df.groupby("position_group")["c"].sum().sort_values(ascending=False).to_string())
    print("n positions", len(df), "→", CONFIG_CSV)
