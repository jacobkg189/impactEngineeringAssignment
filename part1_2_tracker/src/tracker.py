"""
tracker.py — SYSTEM side. Runs one Kalman filter per track_id, in real time.

Input:  REPORTS table (radar feed only — this file never touches truth).
Output: ESTIMATES table (see common/files.py): every 0.1 s, for every object
        being tracked: position, velocity, how unsure, how stale, and a fit
        score (does it move like a straight-line flyer?).

REAL TIME: the Tracker is fed one 0.1 s tick at a time via step(). At tick t it
has only seen reports with time <= t. The decision code (Part 1.3) will run
inside this same loop, so "the moment we decided" really is a moment in time.

Track life cycle:
  - first report with a new track_id   -> start a new filter
  - each tick                          -> predict every filter to now
  - a report for that track this tick  -> update that filter
  - no report for TRACK_DROP_AFTER_S   -> forget the track
"""

from collections import deque

import numpy as np

from common import config as cfg
from common.files import ESTIMATE_DTYPE
from .kalman import ConstantVelocityKalman


class Tracker:

    def __init__(self, process_noise_q=cfg.TRACKER_PROCESS_NOISE):
        self.q = process_noise_q
        self.filters = {}          # track_id -> ConstantVelocityKalman
        self.last_report = {}      # track_id -> time of last report
        self.n_reports = {}        # track_id -> count
        self.nis_history = {}      # track_id -> deque of (time, NIS) for the fit score

    def step(self, time_s, reports_now):
        """Advance to time_s, absorb this tick's reports, return estimates rows."""
        # 1. Everyone moves forward to "now".
        for kf in self.filters.values():
            kf.predict(time_s)

        # 2. Blend in whatever arrived this tick (or start new tracks).
        for r in reports_now:
            tid = str(r["track_id"])
            z = np.array([r["x_m"], r["y_m"], r["z_m"]])
            if tid not in self.filters:
                self.filters[tid] = ConstantVelocityKalman(
                    z, time_s, cfg.RADAR_SIGMA_M, self.q, cfg.TRACKER_INIT_VEL_SIGMA_MPS)
                self.n_reports[tid] = 0
                self.nis_history[tid] = deque()
            else:
                nis = self.filters[tid].update(z)
                history = self.nis_history[tid]
                history.append((time_s, nis))
                while history[0][0] <= time_s - cfg.TRACKER_FIT_WINDOW_S:
                    history.popleft()
            self.last_report[tid] = time_s
            self.n_reports[tid] += 1

        # 3. Forget tracks that went quiet for too long.
        for tid in [t for t, last in self.last_report.items()
                    if time_s - last > cfg.TRACK_DROP_AFTER_S]:
            del self.filters[tid], self.last_report[tid], self.n_reports[tid], self.nis_history[tid]

        return [self._estimate_row(tid, time_s) for tid in sorted(self.filters)]

    def _estimate_row(self, tid, time_s):
        kf = self.filters[tid]
        return (tid, time_s, *kf.position, *kf.velocity,
                kf.position_error_m, kf.velocity_error_mps,
                self.n_reports[tid], time_s - self.last_report[tid], self.fit_score(tid))

    def fit_score(self, tid):
        """Average NIS over the last few seconds. NaN until the window is at
        least half full — too few reports to judge."""
        history = self.nis_history[tid]
        enough = 0.5 * cfg.TRACKER_FIT_WINDOW_S * cfg.RADAR_RATE_HZ
        if len(history) < enough:
            return float("nan")
        return float(np.mean([nis for _, nis in history]))


def ticks(reports):
    """Group the report stream into 0.1 s ticks: yields (time_s, reports_at_that_tick).

    Includes ticks where nothing arrived, so filters keep predicting through gaps.
    """
    tick_index = np.round(reports["time_s"] / cfg.RADAR_DT_S).astype(int)
    for k in range(tick_index.min(), tick_index.max() + 1):
        yield k * cfg.RADAR_DT_S, reports[tick_index == k]


def run_tracker(reports, process_noise_q=cfg.TRACKER_PROCESS_NOISE):
    """Convenience: run the whole report stream through a Tracker."""
    tracker = Tracker(process_noise_q)
    rows = []
    for time_s, reports_now in ticks(reports):
        rows.extend(tracker.step(time_s, reports_now))
    return np.array(rows, dtype=ESTIMATE_DTYPE)
