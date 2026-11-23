"""
replay.py — JUDGE side (reads truth). What really happened after each launch order?

The decision step (1.3) only made a plan. It gave the order at t, the interceptor leaves
3 s later, flies a straight line to the aim point, and should meet the object there at the
expected time. This file flies that plan against the TRUE path and measures how close the two
really got. Both pictures (the 3D page and the PNG) are drawn from what this returns.

  true_position(truth, tid, times)          where an object really was (NaN when it didn't exist)
  interceptor_position(launch, times)       absent before the order, in the container until it
                                            leaves, then a straight line through the aim point
  replay_launch(launch, truth)              the true closest pass -> Engagement
  shown_object_position / shown_interceptor_position
                                            the same, but stopped at the contact for the pictures

THE GENERATOR DOESN'T KNOW ABOUT THE INTERCEPTOR: in truth.csv and reports.csv the object
keeps flying after the contact. The pictures stop it at the contact. The rest of its true path
is drawn as a faint dotted line, and its reports after the contact are left out.
"""

from dataclasses import dataclass

import numpy as np

from common import config as cfg
from common.files import positions, rows_for

PASS_SEARCH_DT_S = 0.01        # time step for finding the closest pass (closing speed ~85 m/s -> < 1 m per step)
PASS_SEARCH_AFTER_S = 10.0     # keep looking this long after the expected meeting, in case the object is late
SHOW_MISS_FOR_S = 5.0          # after a miss, show the interceptor flying on for this long, then hide it


@dataclass
class Engagement:
    """One launch order, replayed against the truth."""
    track_id: str
    order_time_s: float          # the launch order
    leave_time_s: float          # order + 3 s
    expected_time_s: float       # when the decision step expected the meeting
    aim: np.ndarray              # the planned meeting point (decision output)
    pass_time_s: float           # when interceptor and object were REALLY closest
    pass_distance_m: float       # ...and how close: the true miss distance
    object_at_pass: np.ndarray
    interceptor_at_pass: np.ndarray
    aim_error_m: float           # true object position at the expected time vs the aim point

    @property
    def contact(self):
        """They touched: the object came within the interceptor's reach (touch radius)."""
        return bool(self.pass_distance_m <= cfg.TOUCH_RADIUS_M)

    @property
    def contact_range_m(self):
        """How far from the site they met (measured at the object)."""
        return float(np.linalg.norm(self.object_at_pass))

    @property
    def meeting_point(self):
        return (self.object_at_pass + self.interceptor_at_pass) / 2


def aim_point(launch):
    return np.array([launch["aim_x_m"], launch["aim_y_m"], launch["aim_z_m"]], dtype=float)


def true_position(truth, tid, times):
    """Where object `tid` really was at each time. The truth is on a 0.1 s grid, so this
    interpolates linearly between ticks. Returns (N, 3), NaN outside the object's life."""
    times = np.atleast_1d(np.asarray(times, dtype=float))
    out = np.full((len(times), 3), np.nan)
    rows = rows_for(truth, tid)
    if len(rows) == 0:
        return out
    p = positions(rows)
    alive = (times >= rows["time_s"][0] - 1e-9) & (times <= rows["time_s"][-1] + 1e-9)
    for k in range(3):
        out[alive, k] = np.interp(times[alive], rows["time_s"], p[:, k])
    return out


def interceptor_position(launch, times):
    """Where the interceptor was. NaN before the order, at the origin (in the container) until
    it leaves, then a straight line from the origin through the aim point at
    INTERCEPTOR_SPEED_MPS. It does not stop at the aim point, because a straight-line flyer
    doesn't. Returns (N, 3)."""
    times = np.atleast_1d(np.asarray(times, dtype=float))
    aim = aim_point(launch)
    direction = aim / np.linalg.norm(aim)
    flown = np.clip(times - launch["leave_time_s"], 0.0, None) * cfg.INTERCEPTOR_SPEED_MPS
    out = flown[:, None] * direction
    out[times < launch["time_s"]] = np.nan
    return out


def replay_launch(launch, truth):
    """Fly one launch order against the truth and find the true closest pass."""
    tid = str(launch["track_id"])
    start, end = launch["leave_time_s"], launch["intercept_time_s"] + PASS_SEARCH_AFTER_S
    n = int(np.ceil((end - start) / PASS_SEARCH_DT_S)) + 1
    times = start + np.arange(n) * PASS_SEARCH_DT_S          # integer * dt: no drift
    obj = true_position(truth, tid, times)
    icp = interceptor_position(launch, times)
    gap = np.linalg.norm(obj - icp, axis=1)

    if np.all(np.isnan(gap)):                                 # object gone before the interceptor left
        i, pass_distance = 0, float("inf")
    else:
        i = int(np.nanargmin(gap))
        pass_distance = float(gap[i])

    expected = true_position(truth, tid, launch["intercept_time_s"])[0]
    return Engagement(
        track_id=tid,
        order_time_s=float(launch["time_s"]),
        leave_time_s=float(launch["leave_time_s"]),
        expected_time_s=float(launch["intercept_time_s"]),
        aim=aim_point(launch),
        pass_time_s=float(times[i]),
        pass_distance_m=pass_distance,
        object_at_pass=obj[i],
        interceptor_at_pass=icp[i],
        aim_error_m=float(np.linalg.norm(expected - aim_point(launch))),
    )


def replay_all(launches, truth):
    """One Engagement per launch order, in order."""
    return [replay_launch(L, truth) for L in launches]


# ------------------------------------------------- positions for the pictures ---
def contact_time(engagements, tid):
    """When object `tid` was stopped by a contact, or inf if it never was."""
    times = [e.pass_time_s for e in engagements if e.track_id == tid and e.contact]
    return min(times) if times else float("inf")


def shown_object_position(truth, tid, times, engagements):
    """True position, but held at the contact point once an interceptor touched it."""
    times = np.atleast_1d(np.asarray(times, dtype=float))
    out = true_position(truth, tid, times)
    for e in engagements:
        if e.track_id == tid and e.contact:
            out[times >= e.pass_time_s] = e.object_at_pass
    return out


def shown_interceptor_position(launch, engagement, times):
    """Interceptor position, held at the contact point on a hit, or hidden a few seconds
    after its closest pass on a miss."""
    times = np.atleast_1d(np.asarray(times, dtype=float))
    out = interceptor_position(launch, times)
    if engagement.contact:
        out[times >= engagement.pass_time_s] = engagement.interceptor_at_pass
    else:
        out[times > engagement.pass_time_s + SHOW_MISS_FOR_S] = np.nan
    return out


def latest_row_at(table, tid, time_s):
    """The newest row of `tid` with time <= time_s (tracker estimates or decisions), or None
    if the track was not being tracked at that moment."""
    rows = rows_for(table, tid)
    i = np.searchsorted(rows["time_s"], time_s + 1e-6) - 1
    if i < 0 or time_s - rows["time_s"][i] > cfg.RADAR_DT_S * 1.5:
        return None
    return rows[i]


def first_confirmed_time(decisions, tid):
    """When the decision step first said 'this is a threat, held long enough'."""
    rows = rows_for(decisions, tid)
    hit = rows["time_s"][np.isin(rows["status"], ["confirmed", "launch"])]
    return float(hit[0]) if len(hit) else float("nan")
