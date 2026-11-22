"""
geometry.py — pure math, no state, no randomness, no config. Easy to unit-test.

Everything assumes the target keeps flying in a straight line at constant
velocity — exactly what the tracker estimates. The site is at the origin.

  closest_approach(pos, vel)          how close the object will get to the site, and when
  prediction_sigma(...)               how wrong a position predicted T seconds ahead will be
  solve_intercept(pos, vel, ...)      where/when an interceptor ordered NOW meets the target
  solve_shared_intercept(...)         one interceptor aimed between two targets (their midpoint)
  time_until_latest_launch(...)       how long we can still wait before the intercept
                                      would happen inside a given range

THE INTERCEPT SOLVE
  The interceptor leaves the origin `delay` seconds after the order and flies
  straight at `speed`. Let p' = pos + vel*delay be the target when it leaves.
  After a further tau seconds the target is at p' + vel*tau and the interceptor
  can be anywhere within speed*tau of the origin. They meet when

        |p' + vel*tau| = speed*tau
     => (vel.vel - speed^2) tau^2 + 2 (p'.vel) tau + p'.p' = 0

  a quadratic in tau. Every object here is slower than the interceptor, so the
  tau^2 coefficient is negative and there is exactly one positive root.
"""

import math

import numpy as np


def closest_approach(pos, vel):
    """(distance_m, seconds_from_now) of the object's closest point to the origin.

    If the object is already moving away (closest point in the past), returns
    its current range and 0.
    """
    pos = np.asarray(pos, dtype=float)
    vel = np.asarray(vel, dtype=float)
    speed2 = float(vel @ vel)
    if speed2 <= 0.0:
        return float(np.linalg.norm(pos)), 0.0
    t = -float(pos @ vel) / speed2
    if t <= 0.0:
        return float(np.linalg.norm(pos)), 0.0
    return float(np.linalg.norm(pos + vel * t)), t


def prediction_sigma(pos_err_m, vel_err_mps, horizon_s):
    """1-sigma error of a position predicted horizon_s ahead: the position
    error now, plus the velocity error grown over the horizon."""
    return float(math.hypot(pos_err_m, vel_err_mps * horizon_s))


def solve_intercept(pos, vel, delay_s, speed_mps):
    """Where and when an interceptor ordered NOW meets a straight-flying target.

    Returns (time_to_intercept_s, aim_point), both measured from the order, or
    None when the target cannot be caught (faster than the interceptor and
    pulling away).
    """
    pos = np.asarray(pos, dtype=float)
    vel = np.asarray(vel, dtype=float)
    p = pos + vel * delay_s                 # target when the interceptor leaves
    a = float(vel @ vel) - speed_mps ** 2
    b = float(p @ vel)
    c = float(p @ p)

    if abs(a) < 1e-9:                       # same speed: the quadratic degenerates to a line
        if b >= 0.0:
            return None
        tau = -c / (2.0 * b)
    else:
        disc = b * b - a * c
        if disc < 0.0:
            return None
        root = math.sqrt(disc)
        candidates = [t for t in ((-b - root) / a, (-b + root) / a) if t >= 0.0]
        if not candidates:
            return None
        tau = min(candidates)
    return delay_s + tau, p + vel * tau


def intercept_range(pos, vel, delay_s, speed_mps):
    """Distance from the site at which an intercept ordered now would happen (NaN if impossible)."""
    solution = solve_intercept(pos, vel, delay_s, speed_mps)
    if solution is None:
        return float("nan")
    return float(np.linalg.norm(solution[1]))


def solve_shared_intercept(pos1, vel1, pos2, vel2, delay_s, speed_mps):
    """One interceptor for two straight-flying targets, aimed at their midpoint.

    The midpoint of two constant-velocity points is itself a constant-velocity point, so this is
    solve_intercept() on the midpoint. Returns (time_to_intercept_s, aim_point, separation_m),
    where separation is how far apart the two targets are at that moment, or None if the
    midpoint cannot be caught.
    """
    pos1, vel1, pos2, vel2 = (np.asarray(v, dtype=float) for v in (pos1, vel1, pos2, vel2))
    solution = solve_intercept((pos1 + pos2) / 2, (vel1 + vel2) / 2, delay_s, speed_mps)
    if solution is None:
        return None
    t, aim = solution
    return t, aim, float(np.linalg.norm((pos1 - pos2) + (vel1 - vel2) * t))


def time_until_latest_launch(pos, vel, delay_s, speed_mps, required_range_m):
    """Seconds we can still wait and have the intercept happen outside required_range_m.

    0    = already inside (launch now or accept a closer intercept)
    inf  = the intercept stays outside the line all the way to the target's
           closest approach (it is not coming close enough to matter)
    Found by bisection between now and the moment of closest approach; while the
    target is approaching, waiting always moves the intercept closer in.
    """
    pos = np.asarray(pos, dtype=float)
    vel = np.asarray(vel, dtype=float)

    def margin(wait_s):
        r = intercept_range(pos + vel * wait_s, vel, delay_s, speed_mps)
        return -math.inf if math.isnan(r) else r - required_range_m

    if margin(0.0) <= 0.0:
        return 0.0
    _, t_closest = closest_approach(pos, vel)
    if t_closest <= 0.0 or margin(t_closest) > 0.0:
        return math.inf
    lo, hi = 0.0, t_closest                 # margin(lo) > 0 >= margin(hi)
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        if margin(mid) > 0.0:
            lo = mid
        else:
            hi = mid
    return lo
