"""
Run Part 1.3 on its own (needs Part 1.2's output for this seed):

    .venv/bin/python -m part1_3_decision.run --seed 0

Reads   part1_2_tracker/output/estimates_seed0.csv        (tracker output only — no truth)
Writes  part1_3_decision/output/decisions_seed0.csv       status + numbers, per object, per tick
        part1_3_decision/output/launches_seed0.csv        the launch orders and why
        part1_3_decision/output/decision_seed0.png        why and when, as a picture (no truth either)

This step never opens truth. Judging the launches is Part 1.4 / 1.5's job.
"""

import argparse

import numpy as np

from common import config as cfg
from common.files import read_estimates, rows_for, write_table
from common.paths import DECISION_OUTPUT, estimates_csv, decisions_csv, launches_csv
from part1_3_decision.src.decision import run_decision
from part1_3_decision.src.plot_decision import plot_decision


def run(seed):
    estimates = read_estimates(estimates_csv(seed))
    decisions, launches = run_decision(estimates)
    DECISION_OUTPUT.mkdir(parents=True, exist_ok=True)
    write_table(decisions, decisions_csv(seed))
    write_table(launches, launches_csv(seed))
    png = DECISION_OUTPUT / f"decision_seed{seed}.png"
    plot_decision(decisions, launches, png, title=f"Decision: why and when — seed {seed}")

    print(f"[1.3 decision]  seed {seed}: {len(launches)} launch order(s)")
    for L in launches:
        print(f"                LAUNCH at {L['track_id']}  t = {L['time_s']:.1f} s  ->  leaves {L['leave_time_s']:.1f} s, "
              f"meets it at {L['intercept_time_s']:.1f} s, {L['intercept_range_m']:.0f} m out "
              f"(aim {L['aim_x_m']:.0f}, {L['aim_y_m']:.0f}, {L['aim_z_m']:.0f})")
        print(f"                  why: closest approach {L['closest_approach_m']:.0f} ± {L['closest_sigma_m']:.0f} m, "
              f"speed {L['speed_mps']:.1f} m/s, fit {L['fit_nis']:.1f}, held {L['threat_held_s']:.1f} s, "
              f"deadline in {L['deadline_in_s']:.1f} s, expected aim error {L['aim_sigma_m']:.1f} m "
              f"(allowed {cfg.KILL_RADIUS_M:.0f} m)")
    for tid in sorted(set(decisions["track_id"])):
        d = rows_for(decisions, tid)
        statuses, counts = np.unique(d["status"], return_counts=True)
        summary = ", ".join(f"{s} {c / cfg.RADAR_RATE_HZ:.0f} s" for s, c in zip(statuses, counts))
        print(f"                {tid}: {summary}")
    print(f"                wrote part1_3_decision/output/{decisions_csv(seed).name}, {launches_csv(seed).name}, {png.name}")
    return decisions, launches


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=0)
    run(parser.parse_args().seed)
