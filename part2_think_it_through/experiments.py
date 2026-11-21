"""
experiments.py — the runs behind the numbers in answers.md. Every number quoted there is
reproduced here.

    .venv/bin/python -m part2_think_it_through.experiments      (~2 min on 8 cores)
    -> part2_think_it_through/numbers.md

  Q1  launch timing   same 50 seeds, launch moved earlier / later (LAUNCH_LEAD_S, INTERCEPT_MARGIN_M)
  Q2  radar outage    every report removed for 3 s, starting at different moments
  Q5  real radar      the world is worse than the system assumes: more noise, unknown latency,
                      more drops, a faster bird

Changes apply inside one run only; common/config.py is never edited. WORLD changes (radar noise,
drops, bird speed) apply while generating only, so the SYSTEM side still believes the original
numbers. That is the honest case of a radar nobody has measured yet.
"""

from concurrent.futures import ProcessPoolExecutor
from contextlib import contextmanager
from pathlib import Path

import numpy as np

from common import config as cfg
from common.files import rows_for
from part1_1_generator.src.generator import generate
from part1_3_decision.src.decision import decide_live
from part1_5_checks.src.evaluate import as_table, score_run

SEEDS = range(cfg.N_SEEDS)
OUT = Path(__file__).resolve().parent / "numbers.md"

Q1 = [  # (label, system overrides)
    ("at confirmation (earliest)", dict(LAUNCH_LEAD_S=1e9)),
    ("lead 40 s", dict(LAUNCH_LEAD_S=40.0)),
    ("lead 20 s", dict(LAUNCH_LEAD_S=20.0)),
    ("lead 10 s", dict(LAUNCH_LEAD_S=10.0)),
    ("**lead 5 s (ours)**", dict()),
    ("lead 4 s (one second later)", dict(LAUNCH_LEAD_S=4.0)),
    ("lead 0 s", dict(LAUNCH_LEAD_S=0.0)),
    ("lead 0 s, no 100 m margin (latest)", dict(LAUNCH_LEAD_S=0.0, INTERCEPT_MARGIN_M=0.0)),
]
Q2 = [  # (label, outage start s) — 3 s of silence for every object
    ("no outage", None),
    ("t 30–33 s (cruise)", 30.0),
    ("t 72–75 s (ends ~3 s before the launch)", 72.0),
    ("t 75–78 s (launch due at the end)", 75.0),
    ("t 77–80 s (launch due inside it)", 77.0),
    ("t 84–87 s (interceptor in flight)", 84.0),
]
OUTAGE_S = 3.0
Q5 = [  # (label, world overrides, latency s)
    ("radar as assumed", dict(), 0.0),
    ("noise 30 m, tracker assumes 15", dict(RADAR_SIGMA_M=30.0), 0.0),
    ("0.3 s unknown latency", dict(), 0.3),
    ("0.6 s unknown latency", dict(), 0.6),
    ("30% of reports dropped, not 10%", dict(RADAR_DROP_PROB=0.30), 0.0),
    ("bird at 16 m/s, not 12", dict(C_SPEED_MPS=16.0), 0.0),
    ("bird at 20 m/s", dict(C_SPEED_MPS=20.0), 0.0),
]


@contextmanager
def patched(values):
    old = {k: getattr(cfg, k) for k in values}
    for k, v in values.items():
        setattr(cfg, k, v)
    try:
        yield
    finally:
        for k, v in old.items():
            setattr(cfg, k, v)


def run_case(job):
    """One seed under one case. Returns (scored row, did A's threat clock reset after confirmation)."""
    seed, world, system, outage_start, latency = job
    with patched(world):
        truth, reports = generate(seed)
    tick = np.round(reports["time_s"] / cfg.RADAR_DT_S).astype(int)
    if outage_start is not None:
        silent = (tick >= round(outage_start / cfg.RADAR_DT_S)) & \
                 (tick < round((outage_start + OUTAGE_S) / cfg.RADAR_DT_S))
        reports = reports[~silent]
    if latency:
        # Each report arrives `latency` late and is stamped with its arrival time; the system doesn't know.
        reports = reports.copy()
        reports["time_s"] = np.round(reports["time_s"] / cfg.RADAR_DT_S + round(latency / cfg.RADAR_DT_S)) * cfg.RADAR_DT_S
        reports = reports[reports["time_s"] <= cfg.SIM_DURATION_S + 1e-9]
    with patched(system):
        _, decisions, launches = decide_live(reports)
        row = score_run(seed, truth, decisions, launches)
    a = rows_for(decisions, "A")
    confirmed = np.flatnonzero(np.isin(a["status"], ["confirmed", "launch"]))
    reset = False
    if len(confirmed):
        after = a["status"][confirmed[0]:]
        reset = bool(np.isin(after, ["young", "clear", "slow", "erratic", "threat"]).any())
    return row, reset


def run_all(cases):
    """cases: list of (key, world, system, outage_start, latency). Returns {key: (results, resets)}."""
    jobs = [(seed, w, s, o, lat) for _, w, s, o, lat in cases for seed in SEEDS]
    with ProcessPoolExecutor() as pool:
        out = list(pool.map(run_case, jobs, chunksize=4))
    by_case, n = {}, len(SEEDS)
    for i, (key, *_) in enumerate(cases):
        chunk = out[i * n:(i + 1) * n]
        by_case[key] = (as_table([r for r, _ in chunk]), np.array([x for _, x in chunk]))
    return by_case


def main():
    cases = [(f"q1:{lab}", {}, sysv, None, 0.0) for lab, sysv in Q1]
    cases += [(f"q2:{lab}", {}, {}, t0, 0.0) for lab, t0 in Q2]
    cases += [(f"q5:{lab}", w, {}, None, lat) for lab, w, lat in Q5]
    res = run_all(cases)
    n = len(SEEDS)
    f = lambda x: f"{x:.0f}" if np.isfinite(x) else "—"
    g = lambda x: f"{round(x, 1) + 0.0:.1f}" if np.isfinite(x) else "—"   # + 0.0 turns -0.0 into 0.0
    lines = ["# Numbers behind answers.md", "",
             f"_Written by `python -m part2_think_it_through.experiments`: seeds 0–{n - 1}, {n} runs per row. "
             "Do not edit by hand._", ""]

    # ---- Q1 ---------------------------------------------------------------
    lines += ["## Q1 — launching earlier or later", "",
              "| launch rule | order at t (s) | A really out at order (m) | flight (s) | met at, mean (min) (m) "
              "| closest pass mean / max (m) | contact | met outside 500 m |",
              "|---|---|---|---|---|---|---|---|"]
    for lab, _ in Q1:
        r, _ = res[f"q1:{lab}"]
        flight = r["a_planned_range_m"] / cfg.INTERCEPTOR_SPEED_MPS + cfg.INTERCEPTOR_DELAY_S
        lines.append(f"| {lab} | {np.nanmean(r['a_order_time_s']):.1f} | {f(np.nanmean(r['a_range_at_order_m']))} "
                     f"| {g(_nan(np.mean, flight))} | {f(_nan(np.mean, r['a_intercept_range_m']))} "
                     f"({f(_nan(np.min, r['a_intercept_range_m']))}) | {g(_nan(np.mean, r['a_pass_m']))} / "
                     f"{g(_nan(np.max, r['a_pass_m']))} | {int(r['a_contact'].sum())}/{n} | {int(r['a_outside_500'].sum())}/{n} |")

    # ---- Q2 ---------------------------------------------------------------
    base = res["q2:no outage"][0]
    lines += ["", f"## Q2 — the radar goes silent for {OUTAGE_S:g} s", "",
              "| outage | launch later than without it, mean / max (s) | threat clock reset | contact "
              "| met outside 500 m | closest meeting to the site (m) |",
              "|---|---|---|---|---|---|"]
    for lab, _ in Q2:
        r, resets = res[f"q2:{lab}"]
        late = r["a_order_time_s"] - base["a_order_time_s"]
        lines.append(f"| {lab} | {g(_nan(np.mean, late))} / {g(_nan(np.max, late))} | {int(resets.sum())}/{n} "
                     f"| {int(r['a_contact'].sum())}/{n} | {int(r['a_outside_500'].sum())}/{n} "
                     f"| {f(np.nanmin(r['a_intercept_range_m']))} |")

    # ---- Q5 ---------------------------------------------------------------
    lines += ["", "## Q5 — the real radar is not what the software assumes", "",
              "| what is different | met outside 500 m | runs with a launch at B or C | closest pass mean / max (m) "
              "| bird's top speed heading in (m/s) |",
              "|---|---|---|---|---|"]
    for lab, _, _ in Q5:
        r, _ = res[f"q5:{lab}"]
        lines.append(f"| {lab} | {int(r['a_outside_500'].sum())}/{n} | {int((r['wrong_launches'] > 0).sum())}/{n} "
                     f"| {g(_nan(np.mean, r['a_pass_m']))} / {g(_nan(np.max, r['a_pass_m']))} "
                     f"| {g(_nan(np.max, r['c_top_speed_heading_in_mps']))} |")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


def _nan(fn, values):
    """fn over the finite values, NaN if there are none (e.g. no launch at A at all)."""
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    return float(fn(values)) if len(values) else float("nan")


if __name__ == "__main__":
    main()
