"""
radar.py — WORLD side. Turns true paths into what the radar actually reports.

Input:  TRUTH table from scenario.py, a random number generator.
Output: REPORTS table (see files.py):
        - every position gets Gaussian noise, sigma 15 m, on x, y and z
        - every report is independently dropped with probability 0.10
        - velocity is NOT reported: the radar only gives positions, so the
          tracker has to work out velocity itself
"""

import numpy as np

from common import config as cfg
from common.files import REPORT_DTYPE


def observe(truth, rng):
    # Drop: roll a 0..1 number for every true row, keep it if >= 0.10.
    arrived = rng.random(len(truth)) >= cfg.RADAR_DROP_PROB
    seen = truth[arrived]

    reports = np.zeros(len(seen), dtype=REPORT_DTYPE)
    reports["track_id"] = seen["track_id"]
    reports["time_s"] = seen["time_s"]

    # Noise: independent N(0, 15 m) on each axis.
    noise = rng.normal(0.0, cfg.RADAR_SIGMA_M, size=(len(seen), 3))
    reports["x_m"] = seen["x_m"] + noise[:, 0]
    reports["y_m"] = seen["y_m"] + noise[:, 1]
    reports["z_m"] = seen["z_m"] + noise[:, 2]
    return reports   # already in time order, because truth is
