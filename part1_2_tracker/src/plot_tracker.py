"""
plot_tracker.py — JUDGE side (reads truth). How well did the tracker do on one run?

One row per object, three columns, all against time:
  speed           estimated speed vs true speed (bird 12, threat 25, passer 30)
  position error  actual error vs the error the filter CLAIMS — if the two
                  lines track each other, the filter's confidence is trustworthy
  fit score       average NIS over 5 s: ~3 = flies like a straight line
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from common import config as cfg
from common.files import rows_for
from common.style import COLORS, NAMES, SURFACE, INK, INK_MUTED, ZONE, style_axes
from .compare import errors, velocities


def plot_tracker(truth, estimates, path, title=""):
    fig, axes = plt.subplots(3, 3, figsize=(16, 9.5), sharex=True)
    fig.patch.set_facecolor(SURFACE)

    for row, tid in enumerate("ABC"):
        est = rows_for(estimates, tid)
        true_rows = rows_for(truth, tid)
        pos_err, _, matched = errors(est, truth)
        color = COLORS[tid]
        ax_speed, ax_err, ax_fit = axes[row]
        for ax in axes[row]:
            style_axes(ax)

        # --- speed --------------------------------------------------------
        ax_speed.plot(true_rows["time_s"], np.linalg.norm(velocities(true_rows), axis=1),
                      color=ZONE, linewidth=1.5, linestyle="--", label="truth")
        ax_speed.plot(est["time_s"], np.linalg.norm(velocities(est), axis=1),
                      color=color, linewidth=1.5, label="estimate")
        ax_speed.set_ylim(0, 45)
        ax_speed.set_ylabel(f"{NAMES[tid]}\n\nspeed (m/s)", color=INK_MUTED)

        # --- position error: actual vs claimed ----------------------------
        ax_err.plot(matched["time_s"], pos_err, color=color, linewidth=1, label="actual error")
        ax_err.plot(matched["time_s"], matched["pos_err_m"], color=INK_MUTED, linewidth=1.5,
                    linestyle="--", label="error the filter claims (1σ)")
        ax_err.set_ylim(0, 40 if tid != "C" else None)
        ax_err.set_ylabel("position error (m)", color=INK_MUTED)

        # --- fit score ----------------------------------------------------
        ax_fit.axhline(3, color=ZONE, linewidth=1.2, linestyle="--")
        ax_fit.plot(est["time_s"], est["fit_nis"], color=color, linewidth=1.5)
        ax_fit.text(cfg.SIM_DURATION_S - 1, 3, "3 = straight line", ha="right", va="bottom",
                    fontsize=8, color=INK_MUTED)
        ax_fit.set_ylim(0, max(12, np.nanmax(est["fit_nis"]) * 1.1))
        ax_fit.set_ylabel("fit score (NIS)", color=INK_MUTED)

        if row == 0:
            ax_speed.set_title("Speed: estimate vs truth", loc="left", fontsize=10, color=INK)
            ax_err.set_title("Position error: actual vs what the filter claims", loc="left",
                             fontsize=10, color=INK)
            ax_fit.set_title("Fit score: does it fly like a straight line?", loc="left",
                             fontsize=10, color=INK)
        ax_speed.legend(loc="upper right", fontsize=8, frameon=False)
        ax_err.legend(loc="upper right", fontsize=8, frameon=False)

    for ax in axes[-1]:
        ax.set_xlabel("time (s)", color=INK_MUTED)
        ax.set_xlim(0, cfg.SIM_DURATION_S)
    if title:
        fig.suptitle(title, fontsize=12, color=INK, x=0.06, ha="left")
    fig.tight_layout()
    fig.savefig(path, dpi=120, facecolor=fig.get_facecolor())
    plt.close(fig)
