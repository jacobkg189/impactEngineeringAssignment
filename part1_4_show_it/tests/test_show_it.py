"""
Checks on Part 1.4. Run:  .venv/bin/pytest part1_4_show_it -v

  replay physics   - the interceptor is absent before the order, sits in the container until it
                     leaves, flies at 60 m/s, and is exactly at the aim point at the expected time
  hand cases       - aimed with a perfect estimate: closest pass ~0 m. Same plan, object 30 m off
                     the line: no contact
  real runs        - over 5 seeds: one contact per run, at A, outside 500 m, close to the planned
                     time. The true closest pass is never worse than the aim error.
  held at contact  - after the contact the pictures hold the object and the interceptor still
  3D page          - one frame per slider step, in time order, the page opens on the contact,
                     every frame updates the same traces, the close-up is centred on the meeting
  no launch        - the page and the picture still draw when nothing was launched
  files            - the page is self-contained (plotly.js inside) and the PNG is written
"""

import numpy as np
import pytest

from common import config as cfg
from common.files import LAUNCH_DTYPE, TRUTH_DTYPE, rows_for
from part1_1_generator.src.generator import generate
from part1_3_decision.src.decision import decide_live
from part1_3_decision.src.geometry import solve_intercept
from part1_4_show_it.src.replay import (interceptor_position, replay_all, replay_launch,
                                        shown_interceptor_position, shown_object_position, true_position)
from part1_4_show_it.src.scene3d import CLOSEUP_HALF_M, build_figure, write_html
from part1_4_show_it.src.snapshot import plot_snapshot

SEEDS = range(5)


def pipeline(seed):
    truth, reports = generate(seed)
    estimates, decisions, launches = decide_live(reports)
    return truth, reports, estimates, decisions, launches


@pytest.fixture(scope="module")
def seed0():
    truth, reports, estimates, decisions, launches = pipeline(0)
    return truth, reports, estimates, decisions, launches, replay_all(launches, truth)


def straight_flyer(start, vel, tid="X", duration=100.0):
    """A truth table for one object flying a straight line, on the radar's 0.1 s grid."""
    t = np.arange(int(round(duration / cfg.RADAR_DT_S)) + 1) * cfg.RADAR_DT_S
    table = np.zeros(len(t), dtype=TRUTH_DTYPE)
    table["track_id"], table["time_s"] = tid, t
    pos = np.asarray(start, float) + t[:, None] * np.asarray(vel, float)
    table["x_m"], table["y_m"], table["z_m"] = pos.T
    table["vx_mps"], table["vy_mps"], table["vz_mps"] = vel
    return table


def planned_launch(pos, vel, order_time, tid="X"):
    """A launch row planned the way the decision step plans it (same intercept solve)."""
    flight, aim = solve_intercept(pos, vel, cfg.INTERCEPTOR_DELAY_S, cfg.INTERCEPTOR_SPEED_MPS)
    row = np.zeros(1, dtype=LAUNCH_DTYPE)
    row["track_id"], row["time_s"] = tid, order_time
    row["leave_time_s"] = order_time + cfg.INTERCEPTOR_DELAY_S
    row["intercept_time_s"] = order_time + flight
    row["aim_x_m"], row["aim_y_m"], row["aim_z_m"] = aim
    return row[0]


# ---------------------------------------------------------- replay physics ---
def test_interceptor_waits_then_flies_straight_at_60_mps_to_the_aim_point(seed0):
    launch = seed0[4][0]
    order, leave, meet = launch["time_s"], launch["leave_time_s"], launch["intercept_time_s"]
    assert np.isnan(interceptor_position(launch, order - 0.1)).all()            # not yet ordered
    assert np.allclose(interceptor_position(launch, [order, leave - 0.05]), 0)   # in the container
    aim = np.array([launch["aim_x_m"], launch["aim_y_m"], launch["aim_z_m"]])
    assert np.allclose(interceptor_position(launch, meet)[0], aim, atol=1e-6)    # there on time
    a, b = interceptor_position(launch, [leave + 2.0, leave + 3.0])
    assert np.linalg.norm(b - a) == pytest.approx(cfg.INTERCEPTOR_SPEED_MPS)


def test_true_position_matches_truth_on_ticks_and_is_nan_outside(seed0):
    truth = seed0[0]
    a = rows_for(truth, "A")
    i = len(a) // 2
    assert np.allclose(true_position(truth, "A", a["time_s"][i])[0], [a["x_m"][i], a["y_m"][i], a["z_m"][i]])
    assert np.isnan(true_position(truth, "A", a["time_s"][-1] + 1.0)).all()    # A has reached the site


# ------------------------------------------------------------- hand cases ---
def test_perfect_plan_meets_the_object():
    start, vel = np.array([2000.0, 0.0, 80.0]), np.array([-25.0, 0.0, -1.0])
    truth = straight_flyer(start, vel)
    order = 20.0
    launch = planned_launch(start + vel * order, vel, order)
    e = replay_launch(launch, truth)
    assert e.pass_distance_m < 0.5 and e.contact
    assert e.pass_time_s == pytest.approx(launch["intercept_time_s"], abs=0.02)


def test_object_off_the_planned_line_is_a_miss():
    start, vel = np.array([2000.0, 0.0, 80.0]), np.array([-25.0, 0.0, 0.0])
    truth = straight_flyer(start + [0.0, 30.0, 0.0], vel)       # really flies 30 m to the side
    order = 20.0
    launch = planned_launch(start + vel * order, vel, order)     # plan made for the line without the offset
    e = replay_launch(launch, truth)
    assert e.pass_distance_m == pytest.approx(30.0, abs=1.0)
    assert not e.contact


# --------------------------------------------------------------- real runs ---
@pytest.mark.parametrize("seed", SEEDS)
def test_real_run_meets_A_outside_500_m(seed):
    truth, _, _, _, launches = pipeline(seed)
    engagements = replay_all(launches, truth)
    assert [e.track_id for e in engagements] == ["A"]
    e = engagements[0]
    assert e.contact
    assert e.contact_range_m > cfg.PROTECTED_RADIUS_M
    assert abs(e.pass_time_s - e.expected_time_s) < 0.5
    # The interceptor is AT the aim point at the expected time, so the closest pass over all
    # times can only be as close or closer than the aim error.
    assert e.pass_distance_m <= e.aim_error_m + 0.05


def test_pictures_hold_object_and_interceptor_at_the_contact(seed0):
    truth, _, _, _, launches, engagements = seed0
    e = engagements[0]
    later = np.array([e.pass_time_s, e.pass_time_s + 5, e.pass_time_s + 20])
    assert np.allclose(shown_object_position(truth, "A", later, engagements), e.object_at_pass)
    assert np.allclose(shown_interceptor_position(launches[0], e, later), e.interceptor_at_pass)
    before = e.pass_time_s - 2.0
    assert np.allclose(shown_object_position(truth, "A", before, engagements), true_position(truth, "A", before))


# ----------------------------------------------------------------- 3D page ---
def test_page_frames_slider_and_views_line_up(seed0):
    truth, reports, estimates, decisions, launches, engagements = seed0
    fig = build_figure(truth, reports, estimates, decisions, launches, engagements, title="t")
    frames, steps = fig.frames, fig.layout.sliders[0].steps
    names = [f.name for f in frames]
    assert [s.args[0][0] for s in steps] == names
    assert np.all(np.diff([float(n) for n in names]) > 0)                       # time order
    assert len({tuple(f.traces) for f in frames}) == 1                          # same traces every frame
    active = float(names[fig.layout.sliders[0].active])
    assert active == pytest.approx(engagements[0].pass_time_s, abs=0.01)        # opens on the contact
    views = {b.label: b.args[0] for b in fig.layout.updatemenus[0].buttons}
    close = next(v for label, v in views.items() if label.startswith("Close-up"))
    x0, x1 = close["scene.xaxis.range"]
    assert (x0 + x1) / 2 == pytest.approx(engagements[0].meeting_point[0])
    assert x1 - x0 == pytest.approx(2 * CLOSEUP_HALF_M)


def test_page_and_picture_draw_with_no_launch(tmp_path):
    truth, reports, estimates, decisions, _ = pipeline(0)
    no_launch = np.array([], dtype=LAUNCH_DTYPE)
    fig = build_figure(truth, reports, estimates, decisions, no_launch, [], title="no launch")
    labels = [b.label for b in fig.layout.updatemenus[0].buttons]
    assert labels == ["Whole scene", "Top-down"]
    plot_snapshot(truth, reports, estimates, decisions, no_launch, [], tmp_path / "none.png")
    assert (tmp_path / "none.png").stat().st_size > 0


def test_files_are_written_and_the_page_is_self_contained(seed0, tmp_path):
    truth, reports, estimates, decisions, launches, engagements = seed0
    fig = build_figure(truth, reports, estimates, decisions, launches, engagements, title="t")
    page, png = tmp_path / "replay.html", tmp_path / "replay.png"
    write_html(fig, page, page_title="Replay test")
    plot_snapshot(truth, reports, estimates, decisions, launches, engagements, png, title="t")
    text = page.read_text(encoding="utf-8")
    assert "<title>Replay test</title>" in text
    assert "<script src=" not in text and len(text) > 3_000_000                # plotly.js is embedded, no CDN
    assert png.stat().st_size > 0
