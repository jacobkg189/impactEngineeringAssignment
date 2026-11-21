"""
scenario.py — WORLD side. Builds the TRUE paths of A, B and C.

Input:  a random number generator per object (so runs are reproducible).
Output: a TRUTH table (see files.py), one row per object per 0.1 s tick.

Coordinates: the container is at the origin (0, 0, 0). x/y are horizontal
metres, z is altitude in metres. Velocities are in m/s.

The SYSTEM side (tracker, decision) must never use anything from this module.
"""

import numpy as np

from common import config as cfg
from common.files import TRUTH_DTYPE


def time_grid():
    """Radar tick times: 0.0, 0.1, ..., SIM_DURATION_S.

    Built as integer * dt (not by adding 0.1 repeatedly) so times don't drift
    to values like 12.299999999.
    """
    n_ticks = int(round(cfg.SIM_DURATION_S / cfg.RADAR_DT_S)) + 1
    return np.arange(n_ticks) * cfg.RADAR_DT_S


# ---------------------------------------------------------------------------
# A — the threat: straight line to the site
# ---------------------------------------------------------------------------
def make_threat(t, rng):
    bearing = rng.uniform(0.0, 2 * np.pi)          # which direction it comes from
    start = np.array([
        cfg.A_START_RANGE_M * np.cos(bearing),
        cfg.A_START_RANGE_M * np.sin(bearing),
        cfg.A_ALTITUDE_M,
    ])
    distance_to_site = np.linalg.norm(start)
    velocity = -start / distance_to_site * cfg.A_SPEED_MPS   # unit vector toward origin, times speed

    # A stops existing once it reaches the site (~120 s). Only keep ticks before that.
    t_arrive = distance_to_site / cfg.A_SPEED_MPS
    t = t[t <= t_arrive]

    pos = start + t[:, None] * velocity             # straight line: p(t) = p0 + v*t
    vel = np.tile(velocity, (len(t), 1))            # same velocity on every row
    return _to_table("A", t, pos, vel)


# ---------------------------------------------------------------------------
# B — the passer: straight line that misses by 700-900 m
# ---------------------------------------------------------------------------
def make_passer(t, rng):
    heading = rng.uniform(0.0, 2 * np.pi)
    direction = np.array([np.cos(heading), np.sin(heading), 0.0])
    # The closest point of a straight line to the origin is where the line is
    # perpendicular to the direction of travel. Rotate the direction by 90 deg
    # to get that perpendicular, and walk out `miss` metres along it.
    perpendicular = np.array([-np.sin(heading), np.cos(heading), 0.0])
    miss = rng.uniform(cfg.B_MIN_MISS_M, cfg.B_MAX_MISS_M)
    closest_point = miss * perpendicular + np.array([0.0, 0.0, cfg.B_ALTITUDE_M])
    t_closest = rng.uniform(*cfg.B_T_CLOSEST_S)

    velocity = direction * cfg.B_SPEED_MPS
    pos = closest_point + (t - t_closest)[:, None] * velocity
    vel = np.tile(velocity, (len(t), 1))
    return _to_table("B", t, pos, vel)


# ---------------------------------------------------------------------------
# C — the bird: wanders near the 900 m ring, sometimes dashes at the site
# ---------------------------------------------------------------------------
def make_bird(t, rng):
    dt = cfg.RADAR_DT_S
    bearing = rng.uniform(0.0, 2 * np.pi)
    pos = np.array([
        cfg.C_CENTER_RANGE_M * np.cos(bearing),
        cfg.C_CENTER_RANGE_M * np.sin(bearing),
        cfg.C_ALTITUDE_M,
    ])
    heading = rng.uniform(0.0, 2 * np.pi)
    dash_time_left = 0.0

    all_pos = np.zeros((len(t), 3))
    all_vel = np.zeros((len(t), 3))

    # Step-by-step simulation, because the bird's next move depends on where it is.
    for i in range(len(t)):
        heading_to_site = np.arctan2(-pos[1], -pos[0])

        if dash_time_left > 0:
            # Dashing: fly straight at the site.
            heading = heading_to_site
            dash_time_left -= dt
        else:
            # Maybe start a dash this tick (probability per second * dt = per tick).
            if rng.random() < cfg.C_DASH_PROB_PER_S * dt:
                dash_time_left = rng.uniform(*cfg.C_DASH_DURATION_S)
            # Wander: small random heading change. Scaling by sqrt(dt) makes the
            # amount of wander per second independent of the tick rate.
            heading += cfg.C_TURN_RATE_SIGMA * np.sqrt(dt) * rng.normal()
            # Leash: if too far from the 900 m ring, turn back toward it.
            drift = np.hypot(pos[0], pos[1]) - cfg.C_CENTER_RANGE_M
            if abs(drift) > cfg.C_LEASH_M:
                wanted = heading_to_site if drift > 0 else heading_to_site + np.pi
                heading += cfg.C_LEASH_GAIN * _wrap(wanted - heading) * dt

        vel = cfg.C_SPEED_MPS * np.array([np.cos(heading), np.sin(heading), 0.0])
        all_pos[i] = pos
        all_vel[i] = vel        # the velocity it uses to get from tick i to i+1
        pos = pos + vel * dt

    return _to_table("C", t, all_pos, all_vel)


# ---------------------------------------------------------------------------
def make_truth(rngs):
    """All three objects in one TRUTH table, sorted by time.

    rngs: dict {"A": rng, "B": rng, "C": rng}. Each object has its own random
    stream so that, e.g., changing the bird model doesn't change A's path.
    """
    t = time_grid()
    table = np.concatenate([
        make_threat(t, rngs["A"]),
        make_passer(t, rngs["B"]),
        make_bird(t, rngs["C"]),
    ])
    order = np.lexsort((table["track_id"], table["time_s"]))   # by time, then id
    return table[order]


def _to_table(track_id, t, pos, vel):
    table = np.zeros(len(t), dtype=TRUTH_DTYPE)
    table["track_id"] = track_id
    table["time_s"] = t
    table["x_m"], table["y_m"], table["z_m"] = pos.T
    table["vx_mps"], table["vy_mps"], table["vz_mps"] = vel.T
    return table


def _wrap(angle):
    """Wrap an angle to [-pi, pi] so 'turn by 350 deg' becomes 'turn by -10 deg'."""
    return (angle + np.pi) % (2 * np.pi) - np.pi
