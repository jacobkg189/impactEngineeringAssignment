"""
compare.py — JUDGE side. Grades tracker estimates against the truth.

Used only by tests, tuning and plots. tracker.py / kalman.py never import this.
"""

import numpy as np

from common.files import positions


def velocities(table):
    return np.column_stack([table["vx_mps"], table["vy_mps"], table["vz_mps"]])


def match_truth(rows, truth, time_offset_s=0.0):
    """For each row, the true row of the same object at (row time + offset).

    Returns (truth_rows, found_mask). found_mask is False where no truth exists
    at that time (e.g. A already reached the site).
    """
    key = lambda tid, t: (str(tid), int(round(t * 10)))
    lookup = {key(r["track_id"], r["time_s"]): i for i, r in enumerate(truth)}
    idx = np.array([lookup.get(key(r["track_id"], r["time_s"] + time_offset_s), -1) for r in rows])
    found = idx >= 0
    return truth[np.where(found, idx, 0)], found


def errors(estimates, truth):
    """Actual 3D position and velocity error of every estimate row."""
    true_rows, found = match_truth(estimates, truth)
    pos_err = np.linalg.norm(positions(estimates) - positions(true_rows), axis=1)
    vel_err = np.linalg.norm(velocities(estimates) - velocities(true_rows), axis=1)
    return pos_err[found], vel_err[found], estimates[found]


def prediction_error(estimates, truth, horizon_s):
    """If we extrapolate each estimate in a straight line for horizon_s, how far
    from the truth do we land? This is what matters for aiming the interceptor."""
    future, found = match_truth(estimates, truth, time_offset_s=horizon_s)
    predicted = positions(estimates) + velocities(estimates) * horizon_s
    err = np.linalg.norm(predicted - positions(future), axis=1)
    return err[found], estimates[found]


def rms(values):
    return float(np.sqrt(np.mean(np.square(values)))) if len(values) else float("nan")
