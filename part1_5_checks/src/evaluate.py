"""
evaluate.py — JUDGE side. Allowed to read truth.

One run in, one scored row out (RUN_RESULT_DTYPE in common/files.py):
  - every launch order is flown against the truth (Part 1.4's replay.py): did the interceptor
    really come within KILL_RADIUS_M of its target, and how far from the site?
  - was it launched at A (right) or at B / C (wrong, and a failure)?
  - MARGINS: how close did B and the bird come to being launched at? A clean 0/50 means
    little if every run only just scraped past a threshold.
      B is stopped by the heading-in test:  closest approach + 2 sigma must stay above 500 m
      the bird by the drone-speed test:     estimated speed while heading in, vs 18 m/s
    The same speed is recorded for A from the other side (it must stay above 18 m/s).

"A is the threat" is the scenario's definition, and only the judge knows it. The decision
code never sees the names.
"""

import numpy as np

from common import config as cfg
from common.files import RUN_RESULT_DTYPE, positions, rows_for
from part1_4_show_it.src.replay import replay_all, true_position

THREAT = "A"
NAN = float("nan")


def score_run(seed, truth, decisions, launches):
    """Score one run. Returns one RUN_RESULT_DTYPE row (as a tuple)."""
    engagements = replay_all(launches, truth)
    on_a = [e for e in engagements if e.track_id == THREAT]
    wrong = len(engagements) - len(on_a)

    # A: the first launch at it is the one that counts (the decision step only ever orders one).
    if on_a:
        e = on_a[0]
        L = launches[[str(t) for t in launches["track_id"]].index(THREAT)]
        contact = e.contact
        outside = contact and e.contact_range_m > cfg.PROTECTED_RADIUS_M
        a = (len(on_a), int(contact), int(outside), e.order_time_s,
             float(np.linalg.norm(true_position(truth, THREAT, e.order_time_s)[0])),
             float(np.linalg.norm(e.aim)), e.contact_range_m if contact else NAN, e.pass_distance_m,
             e.aim_error_m, float(L["aim_sigma_m"]),
             _time_to_cross(truth, THREAT, cfg.PROTECTED_RADIUS_M) - e.pass_time_s if contact else NAN)
    else:
        a = (0, 0, 0) + (NAN,) * 8

    a_margin = _margins(decisions, THREAT)
    b_margin = _margins(decisions, "B")
    c_margin = _margins(decisions, "C")
    return (seed, len(engagements), wrong, *a, a_margin["min_speed_heading_in"],
            b_margin["min_band_edge"], b_margin["max_threat_held"],
            c_margin["heading_in_s"], c_margin["top_speed_heading_in"], c_margin["max_threat_held"])


def _margins(decisions, tid):
    """How close each test came to flipping, over the ticks where the tests were really applied
    (not while the track was young, nor after a launch at it)."""
    d = rows_for(decisions, tid)
    judged = d[~np.isin(d["status"], ["young", "launched"])]
    edge = judged["closest_approach_m"] + cfg.THREAT_CONFIDENCE_SIGMA * judged["closest_sigma_m"]
    heading_in = edge < cfg.PROTECTED_RADIUS_M
    speeds = judged["speed_mps"][heading_in]
    return {
        "min_band_edge": float(edge.min()) if len(edge) else NAN,
        "heading_in_s": float(heading_in.sum() * cfg.RADAR_DT_S),
        "top_speed_heading_in": float(speeds.max()) if len(speeds) else NAN,
        "min_speed_heading_in": float(speeds.min()) if len(speeds) else NAN,
        "max_threat_held": float(d["threat_held_s"].max()) if len(d) else 0.0,
    }


def _time_to_cross(truth, tid, radius):
    """When the object really first came within `radius` of the site (inf if never)."""
    rows = rows_for(truth, tid)
    inside = np.flatnonzero(np.linalg.norm(positions(rows), axis=1) <= radius)
    return float(rows["time_s"][inside[0]]) if len(inside) else float("inf")


def as_table(rows):
    return np.array(rows, dtype=RUN_RESULT_DTYPE)
