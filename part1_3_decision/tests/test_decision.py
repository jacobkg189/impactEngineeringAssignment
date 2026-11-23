"""
Checks on the decision step. Run:  .venv/bin/pytest part1_3_decision -v

  geometry       - closest approach and intercept solve against hand-computed cases
  outcome        - over 10 seeds: exactly one launch, at A, intercept outside 500 m,
                   and (judged with truth) A really is within the allowed miss
                   distance of the aim point at the expected time
  timing         - we launch late on purpose, but never past the deadline
  no hard-coding - rename the tracks and the launch still follows the threat
  constraint     - a slower interceptor makes us launch earlier, still outside 500 m
  real time      - decisions up to time t never depend on estimates after t,
                   and the live tracker+decider loop equals the file route
  firewall       - decision code never imports anything that knows the truth
  plot           - the decision picture draws from decisions + launches alone
  two threats    - a second threat arriving with A: the most urgent one goes first, the first
                   launch moves earlier so the next interceptor is ready in time, and both are
                   met outside 500 m. Without that rule the second is met inside 500 m. With no
                   interceptor left, the second is "queued", never launched.
"""

import ast
import math
from pathlib import Path

import numpy as np
import pytest

from common import config as cfg
from common.files import positions, rows_for, write_table, read_launches, read_decisions
from part1_1_generator.src.generator import generate
from part1_2_tracker.src.tracker import run_tracker
from part1_3_decision.src.geometry import (closest_approach, solve_intercept, intercept_range,
                                           time_until_latest_launch)
from part1_3_decision.src.decision import run_decision, decide_live

SEEDS = range(10)
DELAY, SPEED = cfg.INTERCEPTOR_DELAY_S, cfg.INTERCEPTOR_SPEED_MPS


def decided(seed):
    truth, reports = generate(seed)
    estimates = run_tracker(reports)
    decisions, launches = run_decision(estimates)
    return truth, estimates, decisions, launches


def true_position_at(truth, tid, time_s):
    """JUDGE: where the object really was at time_s (linear interpolation)."""
    rows = rows_for(truth, tid)
    p = positions(rows)
    return np.array([np.interp(time_s, rows["time_s"], p[:, k]) for k in range(3)])


# --------------------------------------------------------------- geometry ---
def test_closest_approach_hand_cases():
    d, t = closest_approach([1000, 0, 0], [-25, 0, 0])          # head-on
    assert d == pytest.approx(0.0) and t == pytest.approx(40.0)
    d, t = closest_approach([1000, 800, 0], [-30, 0, 0])        # passes 800 m to the side
    assert d == pytest.approx(800.0) and t == pytest.approx(1000 / 30)
    d, t = closest_approach([1000, 0, 0], [25, 0, 0])           # already moving away
    assert d == pytest.approx(1000.0) and t == 0.0


def test_intercept_solve_head_on_matches_closed_form():
    # Target at R flying straight in at 25 m/s; interceptor leaves 3 s later at 60 m/s.
    # They close at 85 m/s over R - 75 m  ->  flight after leaving = (R - 75) / 85.
    R = 2000.0
    t, aim = solve_intercept([R, 0, 0], [-25, 0, 0], DELAY, SPEED)
    tau = (R - 25 * DELAY) / (25 + SPEED)
    assert t == pytest.approx(DELAY + tau)
    assert np.linalg.norm(aim) == pytest.approx(SPEED * tau)
    assert aim[0] == pytest.approx(R - 25 * t)                  # target really is there at time t


def test_intercept_solve_general_case_is_consistent():
    pos, vel = np.array([1200.0, -700.0, 100.0]), np.array([-20.0, 15.0, -1.0])
    t, aim = solve_intercept(pos, vel, DELAY, SPEED)
    assert np.allclose(aim, pos + vel * t)                        # target is at the aim point at time t
    assert np.linalg.norm(aim) == pytest.approx(SPEED * (t - DELAY))   # interceptor can just reach it
    assert solve_intercept([1000, 0, 0], [0, 0, 0], DELAY, SPEED)[0] == pytest.approx(DELAY + 1000 / SPEED)


def test_cannot_catch_a_faster_target_pulling_away():
    assert solve_intercept([1000, 0, 0], [90, 0, 0], DELAY, SPEED) is None


def test_latest_launch_time_head_on():
    # Intercept range for a head-on target at range R is 60 (R - 75) / 85.
    # It equals 600 m when R = 925 m. From 2000 m at 25 m/s that is 43 s away.
    wait = time_until_latest_launch([2000, 0, 0], [-25, 0, 0], DELAY, SPEED, 600.0)
    assert wait == pytest.approx((2000 - 925) / 25, abs=0.01)
    assert intercept_range([2000 - 25 * wait, 0, 0], [-25, 0, 0], DELAY, SPEED) == pytest.approx(600.0, abs=0.1)
    assert time_until_latest_launch([800, 0, 0], [-25, 0, 0], DELAY, SPEED, 600.0) == 0.0
    assert math.isinf(time_until_latest_launch([1000, 800, 0], [-30, 0, 0], DELAY, SPEED, 600.0))


# ---------------------------------------------------------------- outcome ---
def test_one_launch_at_the_threat_and_it_meets_it_outside_500m():
    for seed in SEEDS:
        truth, _, _, launches = decided(seed)
        assert len(launches) == 1, f"seed {seed}: {len(launches)} launches"
        L = launches[0]
        assert L["track_id"] == "A", f"seed {seed}: launched at {L['track_id']}"
        assert L["intercept_range_m"] > cfg.PROTECTED_RADIUS_M
        # JUDGE with truth: is A really where we aim, when we get there?
        aim = np.array([L["aim_x_m"], L["aim_y_m"], L["aim_z_m"]])
        actual = true_position_at(truth, "A", L["intercept_time_s"])
        miss = np.linalg.norm(aim - actual)
        assert miss < cfg.TOUCH_RADIUS_M, f"seed {seed}: miss {miss:.1f} m"
        assert np.linalg.norm(actual) > cfg.PROTECTED_RADIUS_M


def test_passer_and_bird_never_pass_the_threat_test_for_long():
    for seed in SEEDS:
        _, _, decisions, _ = decided(seed)
        for tid in ("B", "C"):
            held = rows_for(decisions, tid)["threat_held_s"]
            assert held.max() < cfg.THREAT_PERSIST_S, f"seed {seed}: {tid} held {held.max():.1f} s"


# ----------------------------------------------------------------- timing ---
def test_launch_is_late_on_purpose_but_before_the_deadline():
    for seed in SEEDS:
        _, _, decisions, launches = decided(seed)
        L = launches[0]
        assert 0.0 < L["deadline_in_s"] <= cfg.LAUNCH_LEAD_S
        assert L["intercept_range_m"] > cfg.PROTECTED_RADIUS_M + cfg.INTERCEPT_MARGIN_M - 1.0
        # A was a confirmed threat for a long while before we chose to launch.
        a = rows_for(decisions, "A")
        confirmed_for = np.sum(a["status"] == "confirmed") / cfg.RADAR_RATE_HZ
        assert confirmed_for > 30.0, f"seed {seed}: only {confirmed_for:.0f} s confirmed before launch"
        assert np.sum(a["status"] == "launch") == 1


# ----------------------------------------------------------- no hard-coding ---
def test_launch_follows_the_threat_not_the_name():
    """Swap the labels: what the generator calls A arrives as 'C' and vice versa."""
    truth, reports = generate(seed=3)
    renamed = reports.copy()
    swap = {"A": "C", "B": "B", "C": "A"}
    renamed["track_id"] = [swap[t] for t in reports["track_id"]]
    _, launches = run_decision(run_tracker(renamed))
    assert len(launches) == 1 and launches[0]["track_id"] == "C"


# --------------------------------------------------------------- constraint ---
def test_slower_interceptor_means_an_earlier_launch(monkeypatch):
    truth, _, _, normal = decided(4)
    monkeypatch.setattr(cfg, "INTERCEPTOR_SPEED_MPS", 40.0)
    _, _, _, slow = decided(4)
    assert len(slow) == 1 and slow[0]["track_id"] == "A"
    assert slow[0]["time_s"] < normal[0]["time_s"]
    assert slow[0]["intercept_range_m"] > cfg.PROTECTED_RADIUS_M
    actual = true_position_at(truth, "A", slow[0]["intercept_time_s"])
    aim = np.array([slow[0]["aim_x_m"], slow[0]["aim_y_m"], slow[0]["aim_z_m"]])
    assert np.linalg.norm(aim - actual) < cfg.TOUCH_RADIUS_M


# ---------------------------------------------------------------- real time ---
def test_decision_at_time_t_only_uses_estimates_up_to_t():
    _, estimates, decisions, _ = decided(2)
    cut = 60.0
    partial, _ = run_decision(estimates[estimates["time_s"] <= cut])
    early = decisions[decisions["time_s"] <= cut]
    assert len(early) == len(partial)
    for name in early.dtype.names:
        nan_ok = early[name].dtype.kind == "f"
        assert np.array_equal(early[name], partial[name], equal_nan=nan_ok), name


def test_live_loop_equals_file_route():
    _, reports = generate(seed=5)
    estimates, live_decisions, live_launches = decide_live(reports)
    decisions, launches = run_decision(run_tracker(reports))
    for name in decisions.dtype.names:
        nan_ok = decisions[name].dtype.kind == "f"
        assert np.array_equal(decisions[name], live_decisions[name], equal_nan=nan_ok), name
    assert np.array_equal(launches, live_launches)


# ----------------------------------------------------------------- firewall ---
def test_decision_code_never_imports_truth():
    forbidden = ("scenario", "generator", "compare", "truth")
    src = Path(__file__).resolve().parent.parent / "src"
    for name in ("geometry.py", "decision.py", "plot_decision.py"):
        tree = ast.parse((src / name).read_text())
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                module = getattr(node, "module", None) or ""
                names = [module] + [a.name for a in node.names]
                for word in forbidden:
                    assert not any(word in n for n in names), f"{name} imports {names}"


def test_output_files_round_trip(tmp_path):
    _, _, decisions, launches = decided(1)
    write_table(decisions, tmp_path / "d.csv")
    write_table(launches, tmp_path / "l.csv")
    d, l = read_decisions(tmp_path / "d.csv"), read_launches(tmp_path / "l.csv")
    assert np.array_equal(d["status"], decisions["status"])
    assert np.allclose(d["deadline_in_s"], decisions["deadline_in_s"], atol=1e-3, equal_nan=True)
    assert l["track_id"][0] == launches["track_id"][0]
    assert l["intercept_time_s"][0] == pytest.approx(launches["intercept_time_s"][0], abs=1e-3)


def test_plot_draws_without_truth(tmp_path):
    from part1_3_decision.src.plot_decision import plot_decision
    _, _, decisions, launches = decided(0)
    png = tmp_path / "d.png"
    plot_decision(decisions, launches, png)
    assert png.stat().st_size > 50_000


# ------------------------------------------------------- more than one threat ---
TOGETHER = dict(turn_deg=90, delay_s=2.0)      # D: A's flight from another side, 2 s behind it


def two_threats(seed, **second):
    truth, reports = generate(seed, second_threat=second)
    _, decisions, launches = decide_live(reports)
    return truth, decisions, launches


def judged(truth, L):
    """JUDGE: (how far the target really is from the aim point at the planned time,
    how far that is from the site)."""
    aim = np.array([L["aim_x_m"], L["aim_y_m"], L["aim_z_m"]])
    actual = true_position_at(truth, L["track_id"], L["intercept_time_s"])
    return np.linalg.norm(aim - actual), np.linalg.norm(actual)


def test_adding_a_second_threat_does_not_change_A_B_or_C():
    truth, reports = generate(3)
    truth2, reports2 = generate(3, second_threat=TOGETHER)
    assert np.array_equal(truth, truth2[truth2["track_id"] != "D"])
    assert np.array_equal(reports, reports2[reports2["track_id"] != "D"])
    assert "D" in set(reports2["track_id"])


def test_two_threats_most_urgent_first_and_both_met_outside_500m():
    for seed in (1, 2, 3):
        truth, _, launches = two_threats(seed, **TOGETHER)
        assert list(launches["track_id"]) == ["A", "D"], f"seed {seed}"       # A is 2 s ahead: more urgent
        assert list(launches["interceptor"]) == [1, 2]
        assert launches["time_s"][1] >= launches["time_s"][0] + cfg.INTERCEPTOR_REARM_S - 1e-6
        for L in launches:
            miss, out = judged(truth, L)
            assert miss < cfg.TOUCH_RADIUS_M, f"seed {seed}: {L['track_id']} miss {miss:.1f} m"
            assert out > cfg.PROTECTED_RADIUS_M


def test_first_launch_moves_earlier_only_as_much_as_the_next_interceptor_needs():
    _, _, both = two_threats(1, **TOGETHER)
    _, _, _, alone = decided(1)
    earlier_by = alone[0]["time_s"] - both[0]["time_s"]
    assert 0.0 < earlier_by <= cfg.INTERCEPTOR_REARM_S + 0.5
    assert 0.0 < both[1]["deadline_in_s"] <= cfg.LAUNCH_LEAD_S       # the second goes at its normal moment


def test_without_making_time_the_second_threat_waits_and_is_met_inside_500m(monkeypatch):
    monkeypatch.setattr(cfg, "MAKE_TIME_FOR_NEXT", False)
    truth, decisions, launches = two_threats(1, **TOGETHER)
    assert list(launches["track_id"]) == ["A", "D"]
    assert np.sum(rows_for(decisions, "D")["status"] == "queued") > 0     # due, no interceptor ready
    _, out = judged(truth, launches[1])
    assert out < cfg.PROTECTED_RADIUS_M


def test_no_interceptor_left_means_queued_not_launched(monkeypatch):
    monkeypatch.setattr(cfg, "INTERCEPTORS_IN_CONTAINER", 1)
    _, decisions, launches = two_threats(1, **TOGETHER)
    assert list(launches["track_id"]) == ["A"]
    statuses = set(rows_for(decisions, "D")["status"])
    assert "queued" in statuses and "launch" not in statuses


def test_most_urgent_is_not_always_the_closest():
    """A hand-built queue: the far one is faster, so its deadline comes first."""
    from part1_3_decision.src.decision import Decider
    def confirmed(tid, deadline, range_m):
        return dict(tid=tid, flight=10.0, aim=np.array([range_m, 0.0, 0.0]), aim_sigma=5.0, range=range_m,
                    deadline=deadline, why=(0.0, 1.0, 30.0, 3.0, 5.0, deadline, 100, 0.0))
    decider = Decider()
    changed = decider._assign(50.0, [confirmed("near_slow", 12.0, 900.0), confirmed("far_fast", 4.0, 1400.0)])
    assert changed == {"far_fast": "launch"}
    assert decider.launch_table()["track_id"][0] == "far_fast"
