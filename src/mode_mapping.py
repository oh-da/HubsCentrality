"""Map each LINE_ID to its planned mode and attractiveness score."""

from pathlib import Path

import pandas as pd

MODE_FILE = Path(__file__).resolve().parent.parent / "data" / "Lines_and_Planned_Mode_18062026.csv"

MODE_SCORES = {
    "Cable Line": 3,
    "BRT": 4,
    "LRT": 5,
    "Funicular": 2,
    "Metro": 6,
    "Suburban Rail": 6,
    "HighSpeed Rail": 8,
    "Interurban Rail": 7,
}

RAIL_MODES = {"Suburban Rail", "HighSpeed Rail", "Interurban Rail"}

# lines present in the nodes file under a spelling the mode file doesn't use
MANUAL_MODES = {
    "BluRT1": "BRT",   # mode file: BlueRT1
    "BluRT2": "BRT",   # mode file: BlueRT2
    "LRT9": "LRT",     # mode file: LRT91/LRT92 (Jerusalem)
    "LRT10": "LRT",    # mode file: LRT101/LRT102 (Jerusalem)
}


def load_line_modes() -> dict[str, str]:
    """LINE_ID -> Mode_Planned."""
    df = pd.read_csv(MODE_FILE, encoding="cp1255")
    modes = dict(zip(df["Line_ModelName"].astype(str).str.strip(), df["Mode_Planned"].str.strip()))
    modes.update(MANUAL_MODES)
    return modes


def line_score(line_id: str, modes: dict[str, str]) -> int:
    return MODE_SCORES[modes[line_id]]
