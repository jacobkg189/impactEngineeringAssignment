"""
Checks that the generator produces what the PDF describes.
Run:  .venv/bin/pytest -v

Each test is one claim from the PDF (or one of our assumptions), checked on
the generated data. Statistical checks use several seeds and tolerances wide
enough not to fail by bad luck, but tight enough to catch a real bug.
"""

import numpy as np
import pytest

from common import config as cfg
from common.files import positions, rows_for, read_reports, read_truth
from part1_1_generator.src.generator import generate

SEEDS = range(20)


def speeds(table):
    return np.linalg.norm(np.column_stack([table["vx_mps"], table["vy_mps"], table["vz_mps"]]), axis=1)


def ranges(table):
    """3D distance of every row from the site at the origin."""
    return np.linalg.norm(positions(table), axis=1)


def match_reports_to_truth(truth, reports):
    """For each report, find the true row with the same object and tick."""
    key = lambda tid, t: (tid, int(round(t * 10)))
    lookup = {key(r["track_id"], r["time_s"]): i for i, r in enumerate(truth)}
    idx = np.array([lookup[key(r["track_id"], r["time_s"])] for r in reports])
    return truth[idx]


# ----------------------------------------------------------------- radar ---
def test_about_one_in_ten_reports_is_dropped():
    dropped = []
    for seed in SEEDS:
        truth, reports = generate(seed)
        dropped.append(1 - len(reports) / len(truth))
    assert np.mean(dropped) == pytest.approx(cfg.RADAR_DROP_PROB, abs=0.01)


def test_report_noise_is_15m_per_axis_and_unbiased():
    truth, reports = generate(seed=0)
    error = positions(reports) - positions(match_reports_to_truth(truth, reports))
    for axis in range(3):
        assert error[:, axis].std() == pytest.approx(cfg.RADAR_SIGMA_M, rel=0.05)
        assert abs(error[:, axis].mean()) < 1.0


def test_reports_contain_no_velocity():
    _, reports = generate(seed=0)
    assert reports.dtype.names == ("track_id", "time_s", "x_m", "y_m", "z_m")


# --------------------------------------------------------------- objects ---
def test_threat_starts_3km_out_flies_25mps_straight_at_site():
    for seed in SEEDS:
        truth, _ = generate(seed)
        a = rows_for(truth, "A")
        horizontal_start = np.hypot(a["x_m"][0], a["y_m"][0])
        assert horizontal_start == pytest.approx(cfg.A_START_RANGE_M)
        assert np.allclose(speeds(a), cfg.A_SPEED_MPS)
        # "straight at the site": velocity points exactly opposite to position
        pos, vel = positions(a)[0], np.array([a["vx_mps"][0], a["vy_mps"][0], a["vz_mps"][0]])
        cos_angle = pos @ vel / (np.linalg.norm(pos) * np.linalg.norm(vel))
        assert cos_angle == pytest.approx(-1.0)
        assert ranges(a)[-1] < cfg.A_SPEED_MPS * cfg.RADAR_DT_S   # ends at the site


def test_passer_flies_30mps_and_never_comes_within_700m():
    for seed in SEEDS:
        truth, _ = generate(seed)
        b = rows_for(truth, "B")
        assert np.allclose(speeds(b), cfg.B_SPEED_MPS)
        assert ranges(b).min() >= cfg.B_MIN_MISS_M


def test_bird_is_slow_and_stays_around_900m():
    for seed in SEEDS:
        truth, _ = generate(seed)
        c = rows_for(truth, "C")
        assert np.allclose(speeds(c), cfg.C_SPEED_MPS)
        r = ranges(c)
        assert 600 < r.min() and r.max() < 1200


def test_bird_sometimes_heads_straight_at_the_site():
    """The trap: during a dash the bird's velocity points at the site."""
    seeds_with_dash = 0
    for seed in SEEDS:
        truth, _ = generate(seed)
        c = rows_for(truth, "C")
        pos = positions(c)[:, :2]
        vel = np.column_stack([c["vx_mps"], c["vy_mps"]])
        cos_angle = np.sum(pos * vel, axis=1) / (np.linalg.norm(pos, axis=1) * np.linalg.norm(vel, axis=1))
        if np.any(cos_angle < -0.999):
            seeds_with_dash += 1
    assert seeds_with_dash >= len(SEEDS) * 0.8


# ---------------------------------------------------------- reproducible ---
def test_same_seed_same_data_different_seed_different_data():
    _, r1 = generate(seed=3)
    _, r2 = generate(seed=3)
    _, r3 = generate(seed=4)
    assert np.array_equal(r1, r2)
    assert not np.array_equal(r1[:100], r3[:100])


def test_files_round_trip(tmp_path):
    truth, reports = generate(seed=1, out_dir=tmp_path)
    back_r = read_reports(tmp_path / "reports_seed1.csv")
    back_t = read_truth(tmp_path / "truth_seed1.csv")
    assert np.array_equal(back_r["track_id"], reports["track_id"])
    assert np.allclose(positions(back_r), positions(reports), atol=1e-3)
    assert np.allclose(positions(back_t), positions(truth), atol=1e-3)
