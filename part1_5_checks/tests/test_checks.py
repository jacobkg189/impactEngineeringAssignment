"""
Checks on Part 1.5. Run:  .venv/bin/pytest part1_5_checks -v

A checker that always says "50/50" is worthless, so most of these feed it runs that SHOULD fail
and make sure it notices:
  scoring      - a clean run scores as success. An extra launch at B counts as a wrong launch,
                 an aim point moved 50 m off counts as no contact, and no launch at all counts
                 as a failure.
  margins      - B's tightest call and the bird's top speed match a hand computation from the
                 decisions table
  statistics   - the 95% interval behaves at 0/n and n/n, and the summary counts are right
  parallel     - running seeds in parallel processes gives the same table as one by one
  unseen seeds - 10 seeds from a block nothing was tuned on: A met outside 500 m, no wrong launch
  output       - the summary text and the picture are produced
"""

import numpy as np
import pytest

from common import config as cfg
from common.files import LAUNCH_DTYPE, RUN_RESULT_DTYPE, read_run_results, rows_for, write_table
from part1_1_generator.src.generator import generate
from part1_3_decision.src.decision import decide_live
from part1_3_decision.src.geometry import solve_intercept
from part1_5_checks.src.evaluate import as_table, score_run
from part1_5_checks.src.montecarlo import run_many, summarize, summary_markdown, wilson
from part1_5_checks.src.plot_checks import plot_checks


@pytest.fixture(scope="module")
def seed0():
    truth, reports = generate(0)
    _, decisions, launches = decide_live(reports)
    return truth, decisions, launches


def scored(seed, truth, decisions, launches):
    return as_table([score_run(seed, truth, decisions, launches)])[0]


def launch_at(truth, tid, order_time):
    """A launch row aimed perfectly at `tid` (planned from its TRUE state), as a wrong launch would be."""
    rows = rows_for(truth, tid)
    i = int(np.argmin(np.abs(rows["time_s"] - order_time)))
    pos = np.array([rows["x_m"][i], rows["y_m"][i], rows["z_m"][i]])
    vel = np.array([rows["vx_mps"][i], rows["vy_mps"][i], rows["vz_mps"][i]])
    flight, aim = solve_intercept(pos, vel, cfg.INTERCEPTOR_DELAY_S, cfg.INTERCEPTOR_SPEED_MPS)
    row = np.zeros(1, dtype=LAUNCH_DTYPE)
    row["track_id"], row["time_s"] = tid, order_time
    row["leave_time_s"], row["intercept_time_s"] = order_time + cfg.INTERCEPTOR_DELAY_S, order_time + flight
    row["aim_x_m"], row["aim_y_m"], row["aim_z_m"] = aim
    return row


# ----------------------------------------------------------------- scoring ---
def test_clean_run_is_a_success(seed0):
    r = scored(0, *seed0)
    assert (r["n_launches"], r["wrong_launches"], r["a_launches"]) == (1, 0, 1)
    assert r["a_contact"] == 1 and r["a_outside_500"] == 1
    assert r["a_intercept_range_m"] > cfg.PROTECTED_RADIUS_M
    assert 0 < r["a_spare_s"] < 30
    assert r["a_pass_m"] <= r["a_aim_error_m"] + 0.05


def test_extra_launch_at_B_is_counted_as_wrong(seed0):
    truth, decisions, launches = seed0
    with_b = np.concatenate([launches, launch_at(truth, "B", 40.0)])
    r = scored(0, truth, decisions, with_b)
    assert r["wrong_launches"] == 1 and r["n_launches"] == 2
    assert r["a_outside_500"] == 1                       # A's own result is unchanged
    s = summarize(as_table([tuple(r)]))
    assert s["wrong_runs"] == 1


def test_aim_point_50_m_off_is_no_contact(seed0):
    truth, decisions, launches = seed0
    off = launches.copy()
    off["aim_y_m"] += 50.0
    r = scored(0, truth, decisions, off)
    assert r["a_launches"] == 1 and r["a_contact"] == 0 and r["a_outside_500"] == 0
    assert r["a_pass_m"] > cfg.TOUCH_RADIUS_M


def test_no_launch_at_all_is_a_failure(seed0):
    truth, decisions, _ = seed0
    r = scored(0, truth, decisions, np.array([], dtype=LAUNCH_DTYPE))
    assert r["a_launches"] == 0 and r["a_outside_500"] == 0 and r["wrong_launches"] == 0
    assert np.isnan(r["a_intercept_range_m"])


# ----------------------------------------------------------------- margins ---
def test_margins_match_a_hand_computation(seed0):
    truth, decisions, launches = seed0
    r = scored(0, truth, decisions, launches)
    b = rows_for(decisions, "B")
    b = b[b["status"] != "young"]
    assert r["b_min_band_edge_m"] == pytest.approx(
        np.min(b["closest_approach_m"] + cfg.THREAT_CONFIDENCE_SIGMA * b["closest_sigma_m"]))
    c = rows_for(decisions, "C")
    c = c[c["status"] != "young"]
    heading_in = c["closest_approach_m"] + cfg.THREAT_CONFIDENCE_SIGMA * c["closest_sigma_m"] < cfg.PROTECTED_RADIUS_M
    assert r["c_heading_in_s"] == pytest.approx(heading_in.sum() * cfg.RADAR_DT_S)
    assert r["c_top_speed_heading_in_mps"] == pytest.approx(c["speed_mps"][heading_in].max())
    assert r["c_top_speed_heading_in_mps"] < cfg.DRONE_MIN_SPEED_MPS < r["a_min_speed_mps"]


# -------------------------------------------------------------- statistics ---
def test_wilson_interval_at_the_edges():
    lo, hi = wilson(50, 50)
    assert hi == 1.0 and lo == pytest.approx(0.929, abs=0.001)    # 50/50 is not "100%"
    lo, hi = wilson(0, 50)
    assert lo == 0.0 and hi == pytest.approx(0.071, abs=0.001)
    lo, hi = wilson(25, 50)
    assert lo + hi == pytest.approx(1.0)


def test_summary_counts_a_hand_built_table():
    rows = np.zeros(4, dtype=RUN_RESULT_DTYPE)
    rows["seed"] = range(4)
    rows["a_launches"] = [1, 1, 1, 0]
    rows["a_contact"] = [1, 1, 0, 0]
    rows["a_outside_500"] = [1, 1, 0, 0]
    rows["a_intercept_range_m"] = [600, 700, np.nan, np.nan]
    rows["wrong_launches"] = [0, 2, 0, 1]
    s = summarize(rows)
    assert (s["n"], s["a_ok"], s["wrong_runs"], s["wrong_launches"]) == (4, 2, 2, 3)
    assert s["range_mean"] == pytest.approx(650)


# ---------------------------------------------------------------- parallel ---
def test_parallel_equals_one_by_one():
    seeds = [3, 4, 5]
    a, b = run_many(seeds, workers=1), run_many(seeds, workers=3)
    for name in RUN_RESULT_DTYPE.names:
        assert np.allclose(a[name], b[name], equal_nan=True), name


# ------------------------------------------------------------ unseen seeds ---
def test_unseen_seeds_meet_A_outside_500_m_and_never_launch_at_B_or_C():
    results = run_many(range(2000, 2010))
    assert results["a_outside_500"].all()
    assert (results["wrong_launches"] == 0).all()


# ------------------------------------------------------------------ output ---
def test_summary_picture_and_csv_are_written(seed0, tmp_path):
    results = as_table([score_run(0, *seed0)])
    text = summary_markdown("Test", "seed 0", summarize(results))
    assert "A intercepted outside 500 m" in text and "1 / 1" in text
    plot_checks([("seed 0", results)], tmp_path / "checks.png", title="t")
    assert (tmp_path / "checks.png").stat().st_size > 0
    write_table(results, tmp_path / "r.csv")
    back = read_run_results(tmp_path / "r.csv")
    assert back["a_outside_500"][0] == 1 and back["seed"][0] == 0
