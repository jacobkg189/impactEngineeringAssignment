"""
Run Part 1.5 on its own (standalone: it runs the whole pipeline in memory for every seed):

    .venv/bin/python -m part1_5_checks.run                    # seeds 0-49 and held-out 1000-1049
    .venv/bin/python -m part1_5_checks.run --first-seed 5000  # any other block of 50

Writes  part1_5_checks/output/results_seeds0-49.csv        one scored row per run
        part1_5_checks/output/results_seeds1000-1049.csv
        part1_5_checks/output/summary.md                   the tables quoted in the READMEs
        part1_5_checks/output/checks.png                   every run, and how close it came to failing

To try a changed constraint: edit common/config.py and run this again (~10 s).
"""

import argparse
import time

import numpy as np

from common import config as cfg
from common.files import write_table
from common.paths import CHECKS_OUTPUT
from part1_5_checks.src.montecarlo import run_many, summarize, summary_markdown, wilson
from part1_5_checks.src.plot_checks import plot_checks


def run(first_seed=None, n=cfg.N_SEEDS, workers=None):
    if first_seed is None:
        blocks = [("the PDF's 50 runs", range(0, n)),
                  ("held-out seeds, never used for tuning", range(cfg.HELD_OUT_FIRST_SEED, cfg.HELD_OUT_FIRST_SEED + n))]
    else:
        blocks = [(f"seeds {first_seed}–{first_seed + n - 1}", range(first_seed, first_seed + n))]

    CHECKS_OUTPUT.mkdir(parents=True, exist_ok=True)
    start = time.time()
    scored, sections = [], []
    for label, seeds in blocks:
        results = run_many(seeds, workers=workers)
        tag = f"seeds{seeds[0]}-{seeds[-1]}"
        write_table(results, CHECKS_OUTPUT / f"results_{tag}.csv")
        sections.append(summary_markdown(label[0].upper() + label[1:], f"seeds {seeds[0]}–{seeds[-1]}", summarize(results)))
        scored.append((f"seeds {seeds[0]}–{seeds[-1]}", results))
    every = np.concatenate([r for _, r in scored])
    total = summarize(every)

    lines = ["# Part 1.5 results", "",
             "_Written by `python -m part1_5_checks.run`. Do not edit by hand._", ""]
    if len(scored) > 1:
        lo, _ = total["a_ok_ci"]
        _, hi = total["wrong_ci"]
        lines += [f"**All {total['n']} runs:** A intercepted outside {cfg.PROTECTED_RADIUS_M:g} m in "
                  f"**{total['a_ok']} / {total['n']}**, a launch at B or C in **{total['wrong_runs']} / {total['n']}**, "
                  f"mean intercept **{total['range_mean']:.0f} m** from the site. With 95% confidence, in this "
                  f"simulated world the success rate is at least {100 * lo:.1f}% and the wrong-launch rate "
                  f"at most {100 * hi:.1f}%.", ""]
    lines += ["\n\n".join(sections), ""]
    (CHECKS_OUTPUT / "summary.md").write_text("\n".join(lines), encoding="utf-8")

    title = (f"{total['n']} runs · A intercepted outside {cfg.PROTECTED_RADIUS_M:g} m: {total['a_ok']}/{total['n']} · "
             f"launch at B or C: {total['wrong_runs']}/{total['n']} · mean intercept {total['range_mean']:.0f} m out")
    plot_checks(scored, CHECKS_OUTPUT / "checks.png", title=title)

    print(f"[1.5 checks]    {total['n']} runs in {time.time() - start:.0f} s, scored against the truth")
    for label, results in scored:
        s = summarize(results)
        print(f"                {label}: A intercepted outside {cfg.PROTECTED_RADIUS_M:g} m {s['a_ok']}/{s['n']} · "
              f"launch at B or C {s['wrong_runs']}/{s['n']} · intercept mean {s['range_mean']:.0f} m "
              f"(min {s['range_min']:.0f}, max {s['range_max']:.0f}) · closest pass max {s['pass_max']:.1f} m")
    print(f"                margins: B's band never below {total['b_edge_min']:.0f} m (needs < "
          f"{cfg.PROTECTED_RADIUS_M:g}) · bird's top speed heading in {total['c_speed_max']:.1f} m/s, A's lowest "
          f"{total['a_speed_min']:.1f} m/s (test at {cfg.DRONE_MIN_SPEED_MPS:g})")
    print(f"                wrote part1_5_checks/output/summary.md, checks.png, results_*.csv")
    return scored


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--first-seed", type=int, default=None,
                        help="run one block starting here instead of the default two blocks")
    parser.add_argument("--n", type=int, default=cfg.N_SEEDS)
    parser.add_argument("--workers", type=int, default=None, help="1 = no parallel processes")
    args = parser.parse_args()
    run(args.first_seed, args.n, args.workers)
