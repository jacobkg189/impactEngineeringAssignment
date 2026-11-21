"""
paths.py — where each part reads its input and writes its output.

The data flows through the folders in PDF order:
  part1_1_generator/output  ->  reports + truth CSVs
  part1_2_tracker   reads the generator's reports
  part1_3_decision  reads the tracker's estimates
  ...
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

GENERATOR_OUTPUT = ROOT / "part1_1_generator" / "output"
TRACKER_OUTPUT = ROOT / "part1_2_tracker" / "output"
DECISION_OUTPUT = ROOT / "part1_3_decision" / "output"
SHOW_IT_OUTPUT = ROOT / "part1_4_show_it" / "output"
CHECKS_OUTPUT = ROOT / "part1_5_checks" / "output"


def reports_csv(seed):
    return GENERATOR_OUTPUT / f"reports_seed{seed}.csv"


def truth_csv(seed):
    return GENERATOR_OUTPUT / f"truth_seed{seed}.csv"


def estimates_csv(seed):
    return TRACKER_OUTPUT / f"estimates_seed{seed}.csv"


def decisions_csv(seed):
    return DECISION_OUTPUT / f"decisions_seed{seed}.csv"


def launches_csv(seed):
    return DECISION_OUTPUT / f"launches_seed{seed}.csv"
