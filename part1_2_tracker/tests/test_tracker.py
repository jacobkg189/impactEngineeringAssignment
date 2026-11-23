"""
Checks on the tracker. Run:  .venv/bin/pytest part1_2_tracker -v

  correctness   - with q=0 the Kalman filter must equal a best-fit straight line
  gaps          - uncertainty grows while coasting, shrinks when reports return
  accuracy      - good enough to aim at A (numbers from tune.py, with margin)
  honesty       - the filter's claimed error matches its real error
  fit score     - straight flyers score ~3, the bird clearly higher
  real time     - an estimate at time t never depends on reports after t
  firewall      - tracker code never imports anything that knows the truth
"""

import ast
from pathlib import Path

import numpy as np
import pytest

from common import config as cfg
from common.files import REPORT_DTYPE, positions, rows_for, write_table, read_estimates
from part1_1_generator.src.generator import generate
from part1_2_tracker.src.kalman import ConstantVelocityKalman
from part1_2_tracker.src.tracker import run_tracker
from part1_2_tracker.src.compare import errors, prediction_error, rms

SEEDS = range(10)
WARMUP_S = 10.0


def tracked(seed):
    truth, reports = generate(seed)
    est = run_tracker(reports)
    return truth, reports, est[est["time_s"] >= WARMUP_S]


# ------------------------------------------------------------ correctness ---
def test_with_no_process_noise_filter_equals_best_fit_line():
    """A Kalman filter with q=0 and no prior knowledge is mathematically the
    same as a least-squares straight line through all reports so far."""
    _, reports, _ = tracked(0)
    a = rows_for(reports, "A")
    z = positions(a)
    kf = ConstantVelocityKalman(z[0], a["time_s"][0], cfg.RADAR_SIGMA_M,
                                process_noise_q=0.0, init_vel_sigma_mps=1e6)
    for t, zi in zip(a["time_s"][1:], z[1:]):
        kf.predict(t)
        kf.update(zi)
    for axis in range(3):
        slope, intercept = np.polyfit(a["time_s"], z[:, axis], 1)
        assert kf.velocity[axis] == pytest.approx(slope, abs=1e-3)
        assert kf.position[axis] == pytest.approx(intercept + slope * a["time_s"][-1], abs=1e-2)


# ------------------------------------------------------------------- gaps ---
def test_uncertainty_grows_while_coasting_and_shrinks_on_new_report():
    kf = ConstantVelocityKalman(np.zeros(3), 0.0, cfg.RADAR_SIGMA_M, 0.01, 50.0)
    for k in range(1, 101):                        # 10 s of reports from a still object
        kf.predict(k * 0.1)
        kf.update(np.zeros(3))
    before = kf.position_error_m
    kf.predict(10.0 + 3.0)                         # radar silent for 3 s
    during = kf.position_error_m
    kf.update(np.zeros(3))
    after = kf.position_error_m
    assert during > before
    assert after < during


# --------------------------------------------------------------- accuracy ---
def test_accurate_enough_to_aim_at_straight_flyers():
    for tid in ("A", "B"):
        vel, aim = [], []
        for seed in SEEDS:
            truth, _, est = tracked(seed)
            _, v, _ = errors(rows_for(est, tid), truth)
            a, _ = prediction_error(rows_for(est, tid), truth, horizon_s=15.0)
            vel.extend(v)
            aim.extend(a)
        assert rms(vel) < 0.5,  f"{tid} velocity RMS {rms(vel):.2f} m/s"
        assert rms(aim) < cfg.TOUCH_RADIUS_M, f"{tid} 15 s prediction RMS {rms(aim):.1f} m"


def test_claimed_error_matches_real_error_on_straight_flyers():
    for tid in ("A", "B"):
        actual, claimed = [], []
        for seed in SEEDS:
            truth, _, est = tracked(seed)
            p, _, matched = errors(rows_for(est, tid), truth)
            actual.extend(p)
            claimed.extend(matched["pos_err_m"])
        ratio = rms(actual) / rms(claimed)
        # < 1 is expected: q > 0 makes the filter allow for turns that never happen.
        assert 0.75 < ratio < 1.1, f"{tid} honesty ratio {ratio:.2f}"


# -------------------------------------------------------------- fit score ---
def test_fit_score_separates_straight_flyers_from_the_bird():
    fit = {"A": [], "B": [], "C": []}
    for seed in SEEDS:
        _, _, est = tracked(seed)
        for tid in fit:
            fit[tid].extend(rows_for(est, tid)["fit_nis"])
    for tid in ("A", "B"):
        assert 2.5 < np.nanmedian(fit[tid]) < 3.5
    assert np.nanmedian(fit["C"]) > 6.0


# -------------------------------------------------------------- real time ---
def test_estimate_at_time_t_only_uses_reports_up_to_t():
    _, reports = generate(seed=2)
    cut = 50.0
    full = run_tracker(reports)
    partial = run_tracker(reports[reports["time_s"] <= cut])
    early = full[full["time_s"] <= cut]
    assert len(early) == len(partial)
    for name in early.dtype.names:
        # equal_nan: fit_nis is NaN for young tracks, and NaN != NaN by definition
        nan_ok = early[name].dtype.kind == "f"
        assert np.array_equal(early[name], partial[name], equal_nan=nan_ok), name


def test_track_coasts_through_3s_gap_and_is_dropped_after_long_silence():
    rows = [("X", round(k * 0.1, 1), k * 2.5, 0.0, 100.0) for k in range(101)]          # 0-10 s
    rows += [("X", round(k * 0.1, 1), k * 2.5, 0.0, 100.0) for k in range(131, 151)]   # 13.1-15 s (3 s gap)
    rows += [("Y", round(k * 0.1, 1), 0.0, 0.0, 100.0) for k in range(301)]            # keeps the clock running
    reports = np.sort(np.array(rows, dtype=REPORT_DTYPE), order=["time_s", "track_id"])
    est = run_tracker(reports)
    x_times = rows_for(est, "X")["time_s"]
    assert np.any(np.isclose(x_times, 12.0))                  # still tracked during the 3 s gap
    assert x_times.max() == pytest.approx(15.0 + cfg.TRACK_DROP_AFTER_S)   # gone 5 s after last report


# --------------------------------------------------------------- firewall ---
def test_tracker_code_never_imports_truth():
    """The SYSTEM side must not be able to see the answer key."""
    forbidden = ("scenario", "generator", "compare", "truth")
    src = Path(__file__).resolve().parent.parent / "src"
    for name in ("kalman.py", "tracker.py"):
        tree = ast.parse((src / name).read_text())
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                module = getattr(node, "module", None) or ""
                names = [module] + [a.name for a in node.names]
                for word in forbidden:
                    assert not any(word in n for n in names), f"{name} imports {names}"


def test_estimates_file_round_trip(tmp_path):
    _, _, est = tracked(1)
    write_table(est, tmp_path / "e.csv")
    back = read_estimates(tmp_path / "e.csv")
    assert np.allclose(positions(back), positions(est), atol=1e-3)
    assert np.array_equal(back["n_reports"], est["n_reports"])
