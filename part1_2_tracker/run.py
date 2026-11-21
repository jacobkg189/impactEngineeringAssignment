"""
Run Part 1.2 on its own (needs Part 1.1's output for this seed):

    .venv/bin/python -m part1_2_tracker.run --seed 0

Reads   part1_1_generator/output/reports_seed0.csv          (radar feed only)
Writes  part1_2_tracker/output/estimates_seed0.csv          the tracker's output
        part1_2_tracker/output/tracker_seed0.png            how good it was (uses truth)

Re-tune q:  .venv/bin/python -m part1_2_tracker.src.tune   -> output/tuning.txt
"""

import argparse

import numpy as np

from common.files import read_reports, read_truth, rows_for, write_table
from common.paths import TRACKER_OUTPUT, reports_csv, truth_csv, estimates_csv
from part1_2_tracker.src.tracker import run_tracker
from part1_2_tracker.src.plot_tracker import plot_tracker
from part1_2_tracker.src.compare import errors, prediction_error, rms


def run(seed):
    reports = read_reports(reports_csv(seed))           # SYSTEM: radar feed only
    estimates = run_tracker(reports)
    TRACKER_OUTPUT.mkdir(parents=True, exist_ok=True)
    write_table(estimates, estimates_csv(seed))

    truth = read_truth(truth_csv(seed))                  # JUDGE: grading + plot only
    png = TRACKER_OUTPUT / f"tracker_seed{seed}.png"
    plot_tracker(truth, estimates, png, title=f"Tracker performance — seed {seed}")

    print(f"[1.2 tracker]   seed {seed}: after 10 s warm-up —")
    settled = estimates[estimates["time_s"] >= 10]
    for tid in "ABC":
        pos, vel, _ = errors(rows_for(settled, tid), truth)
        aim, _ = prediction_error(rows_for(settled, tid), truth, 15.0)
        fit = rows_for(settled, tid)["fit_nis"]
        print(f"                {tid}: pos RMS {rms(pos):5.1f} m   vel RMS {rms(vel):5.2f} m/s   "
              f"15 s aim RMS {rms(aim):6.1f} m   median fit {np.nanmedian(fit):5.1f}")
    print(f"                wrote part1_2_tracker/output/{estimates_csv(seed).name}, {png.name}")
    return estimates


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=0)
    run(parser.parse_args().seed)
