"""
plot_world.py — Part 1.1 sanity-check picture. JUDGE side (reads truth).

Does the generated world look like the PDF describes?
  left:  top-down map — true paths (lines) and radar reports (dots)
  right: distance to the site over time, with the 500 m and 700 m lines
"""

import matplotlib
matplotlib.use("Agg")           # draw to files, no window needed
import matplotlib.pyplot as plt
import numpy as np

from common import config as cfg
from common.files import positions, rows_for
from common.style import COLORS, NAMES, SURFACE, INK, INK_MUTED, ZONE, style_axes


def plot_world(truth, reports, path, title=""):
    fig, (ax_map, ax_rng) = plt.subplots(1, 2, figsize=(15, 6.8),
                                         gridspec_kw={"width_ratios": [1, 1.25]})
    fig.patch.set_facecolor(SURFACE)

    # --- left: top-down map --------------------------------------------------
    style_axes(ax_map)
    ax_map.add_patch(plt.Circle((0, 0), cfg.PROTECTED_RADIUS_M, color=ZONE, alpha=0.15, linewidth=0))
    ax_map.add_patch(plt.Circle((0, 0), cfg.PROTECTED_RADIUS_M, fill=False, color=ZONE, linewidth=1.2))
    ax_map.annotate("500 m protected", (0, -cfg.PROTECTED_RADIUS_M), textcoords="offset points",
                    xytext=(0, 6), ha="center", fontsize=8, color=INK_MUTED)
    ax_map.plot(0, 0, marker="s", color=INK, markersize=6)
    for tid in ("A", "B", "C"):
        t_rows, r_rows = rows_for(truth, tid), rows_for(reports, tid)
        ax_map.scatter(r_rows["x_m"], r_rows["y_m"], s=3, color=COLORS[tid], alpha=0.25, linewidths=0)
        ax_map.plot(t_rows["x_m"], t_rows["y_m"], color=COLORS[tid], linewidth=2, label=NAMES[tid])
        ax_map.plot(t_rows["x_m"][0], t_rows["y_m"][0], marker="o", markersize=8,
                    color=COLORS[tid], markeredgecolor="white", markeredgewidth=1.5)
    ax_map.set_aspect("equal")
    lim = cfg.A_START_RANGE_M * 1.08
    ax_map.set_xlim(-lim, lim)
    ax_map.set_ylim(-lim, lim)
    ax_map.set_xlabel("x (m)", color=INK_MUTED)
    ax_map.set_ylabel("y (m)", color=INK_MUTED)
    ax_map.set_title("Top-down view  (line = truth, dots = radar reports, ● = start)",
                     fontsize=10, color=INK, loc="left")
    ax_map.legend(loc="upper right", fontsize=9, frameon=False)

    # --- right: distance to the site over time --------------------------------
    style_axes(ax_rng)
    ax_rng.axhspan(0, cfg.PROTECTED_RADIUS_M, color=ZONE, alpha=0.15, linewidth=0)
    ax_rng.axhline(cfg.PROTECTED_RADIUS_M, color=ZONE, linewidth=1.2)
    ax_rng.axhline(cfg.B_MIN_MISS_M, color=ZONE, linewidth=1, linestyle="--")
    ax_rng.text(cfg.SIM_DURATION_S, cfg.PROTECTED_RADIUS_M, "500 m  ", ha="right", va="bottom",
                fontsize=8, color=INK_MUTED)
    ax_rng.text(cfg.SIM_DURATION_S, cfg.B_MIN_MISS_M, "700 m  ", ha="right", va="bottom",
                fontsize=8, color=INK_MUTED)
    for tid in ("A", "B", "C"):
        t_rows, r_rows = rows_for(truth, tid), rows_for(reports, tid)
        ax_rng.scatter(r_rows["time_s"], np.linalg.norm(positions(r_rows), axis=1),
                       s=3, color=COLORS[tid], alpha=0.25, linewidths=0)
        ax_rng.plot(t_rows["time_s"], np.linalg.norm(positions(t_rows), axis=1),
                    color=COLORS[tid], linewidth=2, label=NAMES[tid])
    ax_rng.set_xlim(0, cfg.SIM_DURATION_S)
    ax_rng.set_ylim(0, None)
    ax_rng.set_xlabel("time (s)", color=INK_MUTED)
    ax_rng.set_ylabel("distance to site (m)", color=INK_MUTED)
    ax_rng.set_title("Distance to the site over time", fontsize=10, color=INK, loc="left")
    ax_rng.legend(loc="upper right", fontsize=9, frameon=False)

    if title:
        fig.suptitle(title, fontsize=12, color=INK, x=0.06, ha="left")
    fig.tight_layout()
    fig.savefig(path, dpi=130, facecolor=fig.get_facecolor())
    plt.close(fig)
