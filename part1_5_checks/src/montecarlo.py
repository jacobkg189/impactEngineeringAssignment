"""
montecarlo.py — runs the whole pipeline over many seeds and sums it up.

For every seed, in memory (nothing is written to the other parts' folders):
    generate(seed)      -> truth, reports                    world
    decide_live(reports)-> estimates, decisions, launches    SYSTEM: sees the reports only
    score_run(...)      -> one scored row                    JUDGE: truth enters only here

Seeds run in parallel processes, so 50 runs take seconds. Changing a constraint in
common/config.py and re-running is quick enough to do live.

The PDF's three numbers, plus how sure we can be of them:
    A intercepted outside 500 m   k / n, with a 95% interval
    runs with a launch at B or C  k / n, with a 95% interval
    intercept distance from site  mean, spread
"""

import math
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from common import config as cfg
from part1_1_generator.src.generator import generate
from part1_3_decision.src.decision import decide_live
from .evaluate import as_table, score_run


def run_one(seed):
    truth, reports = generate(seed)
    _, decisions, launches = decide_live(reports)          # SYSTEM: radar reports only
    return score_run(seed, truth, decisions, launches)     # JUDGE: truth enters here


def run_many(seeds, workers=None):
    """Score every seed. workers=1 runs in this process (tests, debugging). Otherwise it uses
    one process per CPU. Each process re-imports common/config.py, so edit the file rather than
    patching values in memory."""
    seeds = list(seeds)
    if workers == 1:
        rows = [run_one(s) for s in seeds]
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            rows = list(pool.map(run_one, seeds))
    return as_table(rows)


def wilson(k, n, z=1.96):
    """95% Wilson score interval for k successes in n runs. Unlike "k/n +- 2 sigma", it behaves
    at 0/n and n/n: 50/50 does not mean 100%. It means at least ~93% with 95% confidence."""
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, centre - half), min(1.0, centre + half)


def summarize(results):
    """The numbers the README and the plot quote, from a RUN_RESULT table."""
    n = len(results)
    ok = int(results["a_outside_500"].sum())
    wrong_runs = int((results["wrong_launches"] > 0).sum())
    met = results["a_intercept_range_m"][results["a_contact"] == 1]
    passes = results["a_pass_m"][results["a_launches"] > 0]
    with_c_in = results["c_top_speed_heading_in_mps"][np.isfinite(results["c_top_speed_heading_in_mps"])]
    return dict(
        n=n,
        a_ok=ok, a_ok_ci=wilson(ok, n),
        a_launched=int((results["a_launches"] > 0).sum()),
        a_contact=int(results["a_contact"].sum()),
        wrong_runs=wrong_runs, wrong_ci=wilson(wrong_runs, n),
        wrong_launches=int(results["wrong_launches"].sum()),
        range_mean=_stat(np.mean, met), range_min=_stat(np.min, met), range_max=_stat(np.max, met),
        range_sd=_stat(np.std, met),
        pass_mean=_stat(np.mean, passes), pass_p95=_stat(lambda x: np.percentile(x, 95), passes),
        pass_max=_stat(np.max, passes),
        sigma_mean=_stat(np.mean, results["a_aim_sigma_m"][results["a_launches"] > 0]),
        order_min=_stat(np.nanmin, results["a_order_time_s"]), order_max=_stat(np.nanmax, results["a_order_time_s"]),
        order_range_min=_stat(np.nanmin, results["a_range_at_order_m"]),
        order_range_max=_stat(np.nanmax, results["a_range_at_order_m"]),
        spare_mean=_stat(np.nanmean, results["a_spare_s"]), spare_min=_stat(np.nanmin, results["a_spare_s"]),
        b_edge_min=_stat(np.nanmin, results["b_min_band_edge_m"]),
        c_runs_heading_in=len(with_c_in),
        c_heading_in_mean_s=_stat(np.mean, results["c_heading_in_s"]),
        c_speed_max=_stat(np.max, with_c_in),
        a_speed_min=_stat(np.nanmin, results["a_min_speed_mps"]),
        bc_held_max=float(max(results["b_max_threat_held_s"].max(), results["c_max_threat_held_s"].max())) if n else 0.0,
    )


def summary_markdown(label, seeds_text, s):
    """A results section in Markdown, written to output/summary.md and quoted in the README."""
    pct = lambda k: f"{100 * k / s['n']:.0f}%"
    ci = lambda lo_hi: f"{100 * lo_hi[0]:.0f}–{100 * lo_hi[1]:.0f}%"
    return "\n".join([
        f"### {label} ({seeds_text})",
        "",
        "| Check (PDF) | Result | 95% interval |",
        "|---|---|---|",
        f"| A intercepted outside {cfg.PROTECTED_RADIUS_M:g} m | **{s['a_ok']} / {s['n']}** ({pct(s['a_ok'])}) | {ci(s['a_ok_ci'])} |",
        f"| runs with a launch at B or C | **{s['wrong_runs']} / {s['n']}** ({pct(s['wrong_runs'])}) | {ci(s['wrong_ci'])} |",
        f"| intercept distance from the site | **mean {s['range_mean']:.0f} m** "
        f"(min {s['range_min']:.0f}, max {s['range_max']:.0f}, sd {s['range_sd']:.1f}) | |",
        "",
        "| Behind those numbers | |",
        "|---|---|",
        f"| launches at A / contacts | {s['a_launched']} / {s['a_contact']} |",
        f"| true closest pass (interceptor to A) | mean {s['pass_mean']:.1f} m, 95th pct {s['pass_p95']:.1f} m, "
        f"max {s['pass_max']:.1f} m (reach {cfg.TOUCH_RADIUS_M:g} m; claimed 1σ {s['sigma_mean']:.1f} m) |",
        f"| launch order | t = {s['order_min']:.1f}–{s['order_max']:.1f} s, A really "
        f"{s['order_range_min']:.0f}–{s['order_range_max']:.0f} m out |",
        f"| time to spare | contact came {s['spare_mean']:.1f} s (min {s['spare_min']:.1f} s) before A "
        f"would have crossed {cfg.PROTECTED_RADIUS_M:g} m |",
        f"| B's tightest call | closest approach + {cfg.THREAT_CONFIDENCE_SIGMA:g}σ never below "
        f"**{s['b_edge_min']:.0f} m** (a launch needs < {cfg.PROTECTED_RADIUS_M:g} m) |",
        f"| the bird's tightest call | it headed in during {s['c_runs_heading_in']} of {s['n']} runs "
        f"(mean {s['c_heading_in_mean_s']:.0f} s per run); its top speed then was **{s['c_speed_max']:.1f} m/s** "
        f"vs the {cfg.DRONE_MIN_SPEED_MPS:g} m/s drone test |",
        f"| A on the other side of that test | slowest estimated speed while heading in: "
        f"**{s['a_speed_min']:.1f} m/s** |",
        f"| longest B or C held the threat test | {s['bc_held_max']:.1f} s (a launch needs "
        f"{cfg.THREAT_PERSIST_S:g} s) |",
    ])


def _stat(fn, values):
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    return float(fn(values)) if len(values) else float("nan")
