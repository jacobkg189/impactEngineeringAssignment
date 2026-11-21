"""
plot_checks.py — JUDGE side. One picture of every run, and how close each one came to failing.

One dot per run along the x axis, the PDF's 50 seeds first and the 50 held-out seeds after the
divider. Four panels, each with the line a dot must stay on the right side of:

  A: where it was met       distance from the site at contact      must stay above 500 m
  A: how close it passed    true closest pass, interceptor to A    must stay below the 15 m reach
  B: its tightest call      closest approach + 2 sigma, at its smallest   must stay above 500 m
  speed while heading in    the bird's fastest and A's slowest     bird below 18 m/s, A above
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from common import config as cfg
from common.style import COLORS, SURFACE, INK, INK_MUTED, GRID, style_axes

MISS_RED = "#d03b3b"
TITLE = dict(loc="left", fontsize=11, color=INK, pad=16)   # room for the block labels above each panel


def plot_checks(blocks, path, title=""):
    """blocks: list of (label, results table). Drawn side by side along x, split by dividers."""
    fig, axes = plt.subplots(2, 2, figsize=(16, 9.5), layout="constrained")
    fig.patch.set_facecolor(SURFACE)
    (ax_range, ax_pass), (ax_b, ax_speed) = axes
    for ax in axes.flat:
        style_axes(ax)

    x, starts, offset = [], [], 0
    for label, r in blocks:
        starts.append((offset, offset + len(r), label))
        x.append(offset + np.arange(len(r)))
        offset += len(r) + 4                                   # a gap between blocks
    r = np.concatenate([b for _, b in blocks])
    x = np.concatenate(x)
    dot = dict(s=30, linewidths=0.6, edgecolors=SURFACE, zorder=3)

    # --- A: where it was met --------------------------------------------------
    met = r["a_contact"] == 1
    ax_range.scatter(x[met], r["a_intercept_range_m"][met], color=COLORS["A"], label="contact", **dot)
    if (~met).any():
        ax_range.scatter(x[~met], np.zeros((~met).sum()), marker="x", color=MISS_RED, s=50, zorder=4,
                         label="no contact with A")
    _line(ax_range, cfg.PROTECTED_RADIUS_M, f"{cfg.PROTECTED_RADIUS_M:g} m: A must be met outside this")
    mean = np.nanmean(r["a_intercept_range_m"][met]) if met.any() else np.nan
    ax_range.axhline(mean, color=COLORS["A"], lw=1, ls=":", zorder=2)
    ax_range.text(x[-1] + 2, mean, f"mean {mean:.0f} m", va="center", ha="left", fontsize=9, color=INK)
    ax_range.set_ylim(0, 800)
    ax_range.set_ylabel("distance from the site (m)", color=INK_MUTED)
    ax_range.set_title("A: where the interceptor met it", **TITLE)

    # --- A: how close it passed ------------------------------------------------
    launched = r["a_launches"] > 0
    ax_pass.scatter(x[launched], r["a_pass_m"][launched], color=COLORS["A"], **dot)
    _line(ax_pass, cfg.KILL_RADIUS_M, f"{cfg.KILL_RADIUS_M:g} m reach: contact if below")
    sigma = np.nanmean(r["a_aim_sigma_m"][launched]) if launched.any() else np.nan
    ax_pass.axhline(sigma, color=INK_MUTED, lw=1, ls=":")
    ax_pass.text(x[-1] + 2, sigma, f"aim error the\nsystem claimed (1σ)", va="center", ha="left", fontsize=8.5,
                 color=INK_MUTED)
    ax_pass.set_ylim(0, max(20, np.nanmax(r["a_pass_m"]) * 1.1 if launched.any() else 20))
    ax_pass.set_ylabel("true closest pass (m)", color=INK_MUTED)
    ax_pass.set_title("A: how close the interceptor really passed", **TITLE)

    # --- B: tightest heading-in call -------------------------------------------
    k = cfg.THREAT_CONFIDENCE_SIGMA
    ax_b.scatter(x, r["b_min_band_edge_m"], color=COLORS["B"], **dot)
    _line(ax_b, cfg.PROTECTED_RADIUS_M, f"{cfg.PROTECTED_RADIUS_M:g} m: B is 'heading in' only if below")
    wrong = r["wrong_launches"] > 0
    if wrong.any():
        ax_b.scatter(x[wrong], np.full(wrong.sum(), 40), marker="x", color=MISS_RED, s=50, zorder=4,
                     label="launch at B or C")
    ax_b.set_ylim(0, 1000)
    ax_b.set_ylabel(f"closest approach + {k:g}σ (m)", color=INK_MUTED)
    ax_b.set_title(f"B: its tightest call. Smallest 'closest approach + {k:g}σ' over the run",
                   **TITLE)

    # --- speed while heading in ------------------------------------------------
    ax_speed.scatter(x, r["c_top_speed_heading_in_mps"], color=COLORS["C"], label="bird: fastest while heading in",
                     **dot)
    ax_speed.scatter(x, r["a_min_speed_mps"], color=COLORS["A"], label="A: slowest while heading in", **dot)
    _line(ax_speed, cfg.DRONE_MIN_SPEED_MPS, f"{cfg.DRONE_MIN_SPEED_MPS:g} m/s: slower is not a drone")
    ax_speed.set_ylim(0, 32)
    ax_speed.set_ylabel("estimated speed (m/s)", color=INK_MUTED)
    ax_speed.set_title("The drone-speed test: the only thing between the bird and a launch",
                       **TITLE)
    ax_speed.legend(loc="lower right", fontsize=9, frameon=False, ncol=2)

    # --- shared x axis: blocks and dividers -------------------------------------
    for ax in axes.flat:
        for i, (a, b, label) in enumerate(starts):
            if i:
                ax.axvline(a - 2, color=GRID, lw=1.5)
            ax.text((a + b - 1) / 2, 1.0, label, transform=ax.get_xaxis_transform(), ha="center", va="bottom",
                    fontsize=8.5, color=INK_MUTED)
        ax.set_xlim(-2, x[-1] + 14)
        ax.set_xticks([])
        ax.set_xlabel("one dot per run", color=INK_MUTED)

    if title:
        fig.suptitle(title, fontsize=13, color=INK, x=0.01, ha="left")
    fig.savefig(path, dpi=110, facecolor=fig.get_facecolor())
    plt.close(fig)


def _line(ax, y, text):
    """Threshold line with its label on a surface chip, so dots never hide the text."""
    ax.axhline(y, color=INK_MUTED, lw=1.2, ls="--", zorder=1)
    ax.text(0.005, y, text, transform=ax.get_yaxis_transform(), ha="left", va="bottom", fontsize=8.5,
            color=INK_MUTED, bbox=dict(facecolor=SURFACE, edgecolor="none", pad=1.2), zorder=5)
