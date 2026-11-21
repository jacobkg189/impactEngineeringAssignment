"""
tune.py — pick the process noise q by experiment, not by guessing.

For several q values, over many seeds, measure per object (after a 10 s warm-up):
  vel RMS      how wrong the velocity is
  aim@15s RMS  how wrong a 15 s straight-line prediction is  <- what aiming needs
  honesty      actual error / error the filter claims. ~1.0 = the filter's
               confidence can be trusted; >1 = overconfident (dangerous for
               the decision step), <1 = too timid.
  fit (NIS)    median fit score. ~3 = "moves like a straight line". We want
               A and B near 3 and the bird clearly above, so the decision
               step can tell them apart.

    .venv/bin/python -m part1_2_tracker.src.tune
"""

import numpy as np

from common.files import rows_for
from common.paths import TRACKER_OUTPUT
from part1_1_generator.src.generator import generate
from .tracker import run_tracker
from .compare import errors, prediction_error, rms

Q_VALUES = [0.0, 0.001, 0.01, 0.1, 1.0, 10.0]
SEEDS = range(20)
WARMUP_S = 10.0
HORIZON_S = 15.0


def evaluate_q(q):
    acc = {tid: {"vel": [], "aim": [], "pos": [], "claimed": [], "fit": []} for tid in "ABC"}
    for seed in SEEDS:
        truth, reports = generate(seed)
        est = run_tracker(reports, process_noise_q=q)
        est = est[est["time_s"] >= WARMUP_S]
        for tid in "ABC":
            pos_err, vel_err, matched = errors(rows_for(est, tid), truth)
            aim_err, _ = prediction_error(rows_for(est, tid), truth, HORIZON_S)
            acc[tid]["vel"].extend(vel_err)
            acc[tid]["aim"].extend(aim_err)
            acc[tid]["pos"].extend(pos_err)
            acc[tid]["claimed"].extend(matched["pos_err_m"])
            acc[tid]["fit"].extend(matched["fit_nis"])
    return {tid: {"vel": rms(a["vel"]), "aim": rms(a["aim"]),
                  "honesty": rms(a["pos"]) / rms(a["claimed"]),
                  "fit": float(np.nanmedian(a["fit"]))} for tid, a in acc.items()}


def main():
    lines = [f"Tracker tuning over {len(SEEDS)} seeds (after {WARMUP_S:.0f} s warm-up)", "",
             f"{'q':>7} | {'vel RMS (m/s)':^20} | {'aim@15s RMS (m)':^20} | {'honesty (1.0 = good)':^20} | {'fit NIS (3 = straight)':^20}",
             f"{'':>7} |" + " |".join([f"{'A':>7}{'B':>7}{'C':>7}"] * 4),
             "-" * 103]
    for q in Q_VALUES:
        r = evaluate_q(q)
        lines.append(f"{q:>7g} | " + " | ".join(
            "".join(f"{r[t][k]:>{6 if t == 'A' else 7}.2f}" for t in "ABC")
            for k in ("vel", "aim", "honesty", "fit")))
    text = "\n".join(lines)
    print(text)
    TRACKER_OUTPUT.mkdir(parents=True, exist_ok=True)
    (TRACKER_OUTPUT / "tuning.txt").write_text(text + "\n")


if __name__ == "__main__":
    main()
