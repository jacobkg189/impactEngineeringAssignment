"""
decision.py — SYSTEM side. For each track, every tick: launch or not, and when.

Input:  tracker estimates only (never truth, never the track's name).
Output: DECISIONS table — one row per track per tick: a status and every
                          number it was based on (so Part 1.4 can show WHY)
        LAUNCHES  table — one row per launch order: aim point, expected
                          intercept time and range, and the WHY numbers

THE LOGIC, per track, every 0.1 s
  1. Old enough to judge?         age >= MIN_TRACK_AGE_S and fit score exists
                                  -> else "young"
  2. Heading inside 500 m?        closest approach + k*sigma < 500 m
                                  -> else "clear"           (this rules out B)
  3. Moves like a drone?          speed >= DRONE_MIN_SPEED_MPS
                                  -> else "slow"            (this rules out the bird)
     Flies straight?              fit score <= MAX_FIT_NIS
                                  -> else "erratic"         (bird again, when it turns)
  4. Held for a while?            all of the above for THREAT_PERSIST_S without a break
                                  -> else "threat" (watching)
  5. Can we still catch it?       the intercept solve has a solution
                                  -> else "too_late"
  6. Is it time?                  seconds until the intercept would fall inside
                                  500 m + margin  <=  LAUNCH_LEAD_S
                                  -> "launch" now; else "confirmed" (holding)

MORE THAN ONE THREAT (_assign, after every track has been judged this tick)
  Interceptors are limited: one is ready at the start, the next INTERCEPTOR_REARM_S after
  each launch. The confirmed threats are queued, most urgent first. Two flying close enough
  together share one interceptor aimed at their midpoint. Otherwise the most urgent one goes
  first, early enough that the next interceptor is ready in time for the next threat.
  A threat that is due while no interceptor is ready is "queued". With one threat, steps 1-6
  above are exactly what happens.

  Waiting is deliberate: aim error ~ velocity error x flight time, so a later
  launch means a shorter flight and a better aim, and gives the target less
  time to do something unexpected. What waiting costs is margin against the
  500 m line — so we wait until LAUNCH_LEAD_S before that margin is used up,
  and not a tick longer.

REAL TIME: the Decider is fed one tick at a time, exactly like the Tracker.
At tick t it has seen nothing after t. decide_live() runs both in one loop.
"""

import math

import numpy as np

from common import config as cfg
from common.files import DECISION_DTYPE, ESTIMATE_DTYPE, LAUNCH_DTYPE
from part1_2_tracker.src.tracker import Tracker, ticks
from .geometry import (closest_approach, prediction_sigma, solve_intercept, solve_shared_intercept,
                       time_until_latest_launch)

NAN = float("nan")


class Decider:

    def __init__(self):
        self.first_seen = {}       # track_id -> time of first estimate
        self.threat_since = {}     # track_id -> time the threat test started holding without a break
        self.launched = set()      # track_ids an interceptor is already on its way to
        self.launches = []         # LAUNCH_DTYPE rows, in order
        self.interceptors_left = cfg.INTERCEPTORS_IN_CONTAINER
        self.next_ready_s = 0.0    # one interceptor is ready from the start
        self.fired = 0             # interceptors launched so far (numbers them 1, 2, ...)

    def step(self, time_s, estimates_now):
        """Judge every track present at this tick, then decide which confirmed threats get an
        interceptor now (_assign). Returns DECISIONS rows."""
        rows, confirmed = [], []
        for est in estimates_now:
            tid = str(est["track_id"])
            self.first_seen.setdefault(tid, time_s)
            row, candidate = self._judge(tid, time_s, est)
            rows.append(row)
            if candidate is not None:
                confirmed.append(candidate)
        changed = self._assign(time_s, confirmed)          # {track_id: "launch" | "queued"}
        for row in rows:
            row[2] = changed.get(row[0], row[2])
        return [tuple(r) for r in rows]

    # ------------------------------------------------------------------------
    def _judge(self, tid, t, est):
        pos = np.array([est["x_m"], est["y_m"], est["z_m"]])
        vel = np.array([est["vx_mps"], est["vy_mps"], est["vz_mps"]])
        speed = float(np.linalg.norm(vel))
        fit = float(est["fit_nis"])
        age = t - self.first_seen[tid]

        # Where is it going, and how sure are we?
        d_min, t_min = closest_approach(pos, vel)
        d_sigma = prediction_sigma(est["pos_err_m"], est["vel_err_mps"], t_min)

        # If we launched right now: where and when would we meet it?
        solution = solve_intercept(pos, vel, cfg.INTERCEPTOR_DELAY_S, cfg.INTERCEPTOR_SPEED_MPS)
        if solution is None:
            flight, aim, int_range, aim_sigma = NAN, np.full(3, NAN), NAN, NAN
        else:
            flight, aim = solution
            int_range = float(np.linalg.norm(aim))
            aim_sigma = prediction_sigma(est["pos_err_m"], est["vel_err_mps"], flight)
        required = cfg.PROTECTED_RADIUS_M + cfg.INTERCEPT_MARGIN_M
        deadline_in = time_until_latest_launch(pos, vel, cfg.INTERCEPTOR_DELAY_S,
                                               cfg.INTERCEPTOR_SPEED_MPS, required)

        # The tests, in order. The first one that fails names the status.
        heading_in = d_min + cfg.THREAT_CONFIDENCE_SIGMA * d_sigma < cfg.PROTECTED_RADIUS_M
        fast = speed >= cfg.DRONE_MIN_SPEED_MPS
        straight = not math.isnan(fit) and fit <= cfg.MAX_FIT_NIS

        if tid in self.launched:
            status = "launched"
        elif age < cfg.MIN_TRACK_AGE_S or math.isnan(fit):
            status = "young"
        elif not heading_in:
            status = "clear"
        elif not fast:
            status = "slow"
        elif not straight:
            status = "erratic"
        else:
            status = "threat"
        is_threat = status == "threat"

        if is_threat:
            self.threat_since.setdefault(tid, t)
        else:
            self.threat_since.pop(tid, None)
        held = t - self.threat_since[tid] if tid in self.threat_since else 0.0

        candidate = None
        if is_threat and held >= cfg.THREAT_PERSIST_S:
            if solution is None:
                status = "too_late"
            else:
                status = "confirmed"            # _assign decides: launch now, queued, or keep holding
                candidate = dict(tid=tid, pos=pos, vel=vel, pos_err=float(est["pos_err_m"]),
                                 vel_err=float(est["vel_err_mps"]), flight=flight, aim=aim,
                                 aim_sigma=aim_sigma, range=int_range, deadline=deadline_in,
                                 why=(d_min, d_sigma, speed, fit, held, deadline_in,
                                      int(est["n_reports"]), float(est["time_since_report_s"])))

        row = [tid, t, status, age, speed, d_min, d_sigma, fit, int_range, t + flight, *aim, deadline_in, held]
        return row, candidate

    # ------------------------------------------------------------------------
    def _assign(self, t, confirmed):
        """Which confirmed threats get an interceptor now? Returns {track_id: "launch" | "queued"}
        for the tracks whose status changes. Everything else stays "confirmed" (holding).

        1. Most urgent first: least time left before its meeting would fall inside 500 m + margin.
           For threats at the same speed, that is simply the closest one.
        2. Two threats flying close enough together share ONE interceptor aimed at their
           midpoint (_shots, SHARED_SHOT_MARGIN_M).
        3. Every other shot needs its own interceptor. Shot j gets the one that is ready
           j x INTERCEPTOR_REARM_S after this launch, so the first shot goes early enough for every
           later shot to still be on time (MAKE_TIME_FOR_NEXT). With a single threat this is the
           ordinary rule: launch when LAUNCH_LEAD_S is left.
        """
        if not confirmed:
            return {}
        lead = cfg.LAUNCH_LEAD_S
        shots = self._shots(sorted(confirmed, key=lambda c: (c["deadline"], c["range"])))
        due = lambda shot: min(c["deadline"] for c in shot["members"])
        usable = min(len(shots), self.interceptors_left)
        if usable == 0:                                     # none left: say so for every due threat
            return {c["tid"]: "queued" for shot in shots if due(shot) <= lead for c in shot["members"]}
        rearm = cfg.INTERCEPTOR_REARM_S if cfg.MAKE_TIME_FOR_NEXT else 0.0
        if min(due(shots[j]) - j * rearm for j in range(usable)) > lead:
            return {}                                       # every shot can still wait
        if t < self.next_ready_s - 1e-9:                    # due, but the interceptor isn't ready yet
            return {c["tid"]: "queued" for j, shot in enumerate(shots)
                    if j == 0 or due(shot) <= lead for c in shot["members"]}
        self._fire(t, shots[0])
        return {c["tid"]: "launch" for c in shots[0]["members"]}

    def _shots(self, queue):
        """Group the queue (most urgent first) into shots. Each shot is the most urgent threat left,
        plus a partner if one interceptor aimed at their midpoint would have BOTH well inside its
        reach: half their separation at the meeting <= KILL_RADIUS_M - SHARED_SHOT_MARGIN_M."""
        shots, rest = [], list(queue)
        while rest:
            first = rest.pop(0)
            best = None
            for other in rest:
                shared = solve_shared_intercept(first["pos"], first["vel"], other["pos"], other["vel"],
                                                cfg.INTERCEPTOR_DELAY_S, cfg.INTERCEPTOR_SPEED_MPS)
                if shared is not None and shared[2] / 2 <= cfg.KILL_RADIUS_M - cfg.SHARED_SHOT_MARGIN_M \
                        and (best is None or shared[2] < best[1][2]):
                    best = (other, shared)
            if best is None:
                shots.append(dict(members=[first], flight=first["flight"], aim=first["aim"],
                                  aim_sigma=first["aim_sigma"]))
            else:
                other, (flight, aim, _) = best
                rest.remove(other)
                sigma = max(prediction_sigma(c["pos_err"], c["vel_err"], flight) for c in (first, other))
                shots.append(dict(members=[first, other], flight=flight, aim=aim, aim_sigma=sigma))
        return shots

    def _fire(self, t, shot):
        """Launch one interceptor at a shot: one LAUNCH row per threat it is aimed at."""
        self.fired += 1
        self.interceptors_left -= 1
        self.next_ready_s = t + cfg.INTERCEPTOR_REARM_S
        names = [c["tid"] for c in shot["members"]]
        for c in shot["members"]:
            partner = next((n for n in names if n != c["tid"]), "")
            self.launched.add(c["tid"])
            self.launches.append((
                c["tid"], self.fired, partner, t, t + cfg.INTERCEPTOR_DELAY_S, t + shot["flight"], *shot["aim"],
                float(np.linalg.norm(shot["aim"])), shot["flight"], shot["aim_sigma"], *c["why"],
            ))

    def launch_table(self):
        return np.array(self.launches, dtype=LAUNCH_DTYPE)


# ---------------------------------------------------------------- drivers ---
def run_decision(estimates):
    """Feed a whole ESTIMATES table through a Decider, tick by tick.
    Returns (decisions, launches)."""
    decider = Decider()
    rows = []
    for time_s, estimates_now in ticks(estimates):
        rows.extend(decider.step(time_s, estimates_now))
    return np.array(rows, dtype=DECISION_DTYPE), decider.launch_table()


def decide_live(reports):
    """Tracker and Decider in ONE real-time loop over the radar feed.
    Same result as run_decision(run_tracker(reports)) — a test proves it.
    Returns (estimates, decisions, launches)."""
    tracker, decider = Tracker(), Decider()
    est_rows, dec_rows = [], []
    for time_s, reports_now in ticks(reports):
        estimates_now = np.array(tracker.step(time_s, reports_now), dtype=ESTIMATE_DTYPE)
        est_rows.extend(estimates_now)
        dec_rows.extend(decider.step(time_s, estimates_now))
    return (np.array(est_rows, dtype=ESTIMATE_DTYPE),
            np.array(dec_rows, dtype=DECISION_DTYPE),
            decider.launch_table())
