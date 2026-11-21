"""
kalman.py — a constant-velocity Kalman filter for ONE object, in 3D.

THE IDEA IN ONE PARAGRAPH
  The filter keeps a best guess of the object's state (position + velocity)
  AND how unsure it is about that guess (a covariance matrix P). Every tick:
    1. PREDICT  - move the guess forward assuming constant velocity.
                  Uncertainty grows (we're less sure about the future).
    2. UPDATE   - if a radar report arrived, blend it in. The blend weight
                  (the "Kalman gain" K) is decided by comparing how unsure
                  the prediction is vs. how noisy the radar is (15 m).
                  Uncertainty shrinks (we learned something).
  No report this tick? Just skip step 2. That's how missing reports are handled.

THE STATE (6 numbers)
  x = [px, py, pz, vx, vy, vz]     metres and metres/second

THE MATRICES (named as in every textbook, so you can look them up)
  F  "transition"   how the state moves in dt seconds:  p_new = p + v*dt, v_new = v
  Q  "process noise" how much the true motion may differ from constant velocity
  H  "measurement"  what the radar sees of the state: position only, not velocity
  R  "measurement noise"  radar error: 15 m sigma on each axis -> 15^2 on the diagonal
  P  "covariance"   the filter's uncertainty about its own state
"""

import numpy as np

I3 = np.eye(3)
Z3 = np.zeros((3, 3))


class ConstantVelocityKalman:

    def __init__(self, first_position, time_s, radar_sigma_m, process_noise_q, init_vel_sigma_mps):
        self.q = process_noise_q
        self.time_s = time_s

        # Start: position = first report, velocity = 0 but VERY unsure (+-50 m/s).
        # The first few reports quickly pin velocity down.
        self.x = np.concatenate([first_position, np.zeros(3)])
        self.P = np.block([
            [radar_sigma_m**2 * I3, Z3],
            [Z3, init_vel_sigma_mps**2 * I3],
        ])

        self.H = np.hstack([I3, Z3])          # radar sees [px, py, pz]
        self.R = radar_sigma_m**2 * I3

    # ------------------------------------------------------------------ 1 ---
    def predict(self, to_time_s):
        dt = to_time_s - self.time_s
        if dt <= 0:
            return
        F = np.block([
            [I3, dt * I3],
            [Z3, I3],
        ])
        # Process noise for "velocity does a small random walk" (standard
        # 'continuous white-noise acceleration' model). The dt^3/3, dt^2/2, dt
        # terms come from integrating that random acceleration over dt:
        # it nudges velocity, and through velocity, position.
        Q = self.q * np.block([
            [dt**3 / 3 * I3, dt**2 / 2 * I3],
            [dt**2 / 2 * I3, dt * I3],
        ])
        self.x = F @ self.x
        self.P = F @ self.P @ F.T + Q
        self.time_s = to_time_s

    # ------------------------------------------------------------------ 2 ---
    def update(self, measured_position):
        """Blend in one report. Returns the NIS of this report (see below)."""
        H, R, P = self.H, self.R, self.P
        innovation = measured_position - H @ self.x   # report minus where we expected it
        S = H @ P @ H.T + R                           # expected size of that difference
        S_inv = np.linalg.inv(S)
        K = P @ H.T @ S_inv                           # Kalman gain: how much to trust the report
        self.x = self.x + K @ innovation
        # "Joseph form" of the covariance update: same result as the textbook
        # (I - K H) P, but stays numerically symmetric/positive over long runs.
        I_KH = np.eye(6) - K @ H
        self.P = I_KH @ P @ I_KH.T + K @ R @ K.T

        # NIS = "normalised innovation squared": how surprising was this report,
        # measured in units of what the filter expected. For an object that
        # really flies straight it averages 3 (one per axis). Objects that turn,
        # wander or dash keep surprising the filter -> NIS averages well above 3.
        nis = float(innovation @ S_inv @ innovation)
        return nis

    # ------------------------------------------------------------- helpers ---
    @property
    def position(self):
        return self.x[:3]

    @property
    def velocity(self):
        return self.x[3:]

    @property
    def position_error_m(self):
        """1-sigma 3D position uncertainty the filter believes it has."""
        return float(np.sqrt(np.trace(self.P[:3, :3])))

    @property
    def velocity_error_mps(self):
        return float(np.sqrt(np.trace(self.P[3:, 3:])))
