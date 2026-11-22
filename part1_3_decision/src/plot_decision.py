"""
plot_decision.py — why did the decision step do what it did, and when?

Reads only the DECISIONS and LAUNCHES tables (no truth), so this picture shows
exactly what the system knew at each moment. Five panels, one shared time axis:

  verdict          each object's status over time, as a coloured lane
  closest approach where each object will pass the site if it flies on,
                   with the 2-sigma band the threat test uses, vs the 500 m line
  speed            vs the drone-speed threshold
  fit score        vs the "flies straight" threshold
  time left        how long we may still wait before the intercept would fall
                   inside 500 m + margin, vs the launch lead — "late on purpose"

A vertical line across every panel marks each launch order, and a dashed one
the expected intercept time.
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import numpy as np

from common import config as cfg
from common.files import rows_for
from common.style import COLORS, NAMES, SURFACE, INK, INK_MUTED, ZONE, style_axes

# Verdict colours: greys = nothing to do; warm = threat, getting hotter.
# Every wide-enough band also carries its name in text, so colour is never alone.
STATUS_STYLE = {
    "young":     ("#e1e0d9", "young — still judging"),
    "clear":     ("#c3c2b7", "clear — passes outside 500 m"),
    "slow":      ("#898781", "heading in, but too slow for a drone"),
    "erratic":   ("#6f6d68", "heading in, but not flying straight"),
    "threat":    ("#fab219", "threat — watching it hold"),
    "confirmed": ("#ec835a", "confirmed — holding for the launch moment"),
    "queued":    ("#b2452a", "due, but waiting for an interceptor"),
    "launch":    ("#d03b3b", "launch order"),
    "too_late":  ("#d03b3b", "too late to catch"),
    "launched":  ("#52514e", "interceptor on its way"),
}
LABEL_ON_DARK = {"slow", "erratic", "launched", "launch", "too_late", "queued"}


def _threshold(ax, y, text):
    """Dashed threshold line with its label on a surface chip, so data lines never cross the text."""
    ax.axhline(y, color=INK_MUTED, linewidth=1.2, linestyle="--")
    ax.text(cfg.SIM_DURATION_S - 1, y, text, ha="right", va="bottom", fontsize=8, color=INK_MUTED,
            bbox=dict(facecolor=SURFACE, edgecolor="none", pad=1.5), zorder=5)


def _segments(times, statuses):
    """Collapse a per-tick status column into (start, end, status) runs."""
    runs, start = [], 0
    for i in range(1, len(statuses) + 1):
        if i == len(statuses) or statuses[i] != statuses[start]:
            runs.append((times[start], times[i - 1] + cfg.RADAR_DT_S, statuses[start]))
            start = i
    return runs


def plot_decision(decisions, launches, path, title=""):
    track_ids = sorted(set(decisions["track_id"]))
    fig, axes = plt.subplots(5, 1, figsize=(14, 12), sharex=True, layout="constrained",
                             gridspec_kw={"height_ratios": [1.1, 1.4, 1, 1, 1.2]})
    fig.patch.set_facecolor(SURFACE)
    ax_lane, ax_ca, ax_speed, ax_fit, ax_wait = axes
    for ax in axes:
        style_axes(ax)

    # --- verdict lanes ------------------------------------------------------
    for lane, tid in enumerate(reversed(track_ids)):
        d = rows_for(decisions, tid)
        for start, end, status in _segments(d["time_s"], list(d["status"])):
            color, _ = STATUS_STYLE[status]
            ax_lane.broken_barh([(start, end - start)], (lane - 0.38, 0.76),
                                facecolor=color, edgecolor=SURFACE, linewidth=1.5)
            if end - start >= 8:
                ink = "#ffffff" if status in LABEL_ON_DARK else INK
                ax_lane.text((start + end) / 2, lane, status, ha="center", va="center",
                             fontsize=8, color=ink)
    ax_lane.set_yticks(range(len(track_ids)))
    ax_lane.set_yticklabels([NAMES.get(t, t) for t in reversed(track_ids)])
    for label, tid in zip(ax_lane.get_yticklabels(), reversed(track_ids)):
        label.set_color(COLORS.get(tid, INK))
        label.set_fontweight("bold")
    ax_lane.set_ylim(-0.6, len(track_ids) - 0.4)
    ax_lane.grid(False)
    used = [s for s in STATUS_STYLE if s in set(decisions["status"])]
    ax_lane.legend(handles=[Patch(facecolor=STATUS_STYLE[s][0], label=STATUS_STYLE[s][1]) for s in used],
                   loc="lower right", bbox_to_anchor=(1.0, 1.0), ncol=4, fontsize=8, frameon=False)
    ax_lane.set_title("Verdict per object, every 0.1 s", loc="left", fontsize=10, color=INK)

    # --- closest approach with the band the threat test uses ---------------
    k = cfg.THREAT_CONFIDENCE_SIGMA
    for tid in track_ids:
        d = rows_for(decisions, tid)
        live = d["status"] != "launched"            # after launch these numbers no longer drive anything
        t, ca, sig = d["time_s"][live], d["closest_approach_m"][live], d["closest_sigma_m"][live]
        ax_ca.fill_between(t, ca, ca + k * sig, color=COLORS.get(tid, INK), alpha=0.18, linewidth=0)
        ax_ca.plot(t, ca, color=COLORS.get(tid, INK), linewidth=1.5, label=NAMES.get(tid, tid))
    _threshold(ax_ca, cfg.PROTECTED_RADIUS_M, f"{cfg.PROTECTED_RADIUS_M:g} m — protected zone")
    ax_ca.set_ylim(0, 1500)
    ax_ca.set_ylabel("closest approach (m)", color=INK_MUTED)
    ax_ca.legend(loc="upper right", fontsize=8, frameon=False, ncol=len(track_ids))
    ax_ca.set_title(f"Where will it pass the site? Line = estimate, band = up to +{k:g}σ. "
                    f"Heading in only if the whole band is below 500 m",
                    loc="left", fontsize=10, color=INK)

    # --- speed --------------------------------------------------------------
    for tid in track_ids:
        d = rows_for(decisions, tid)
        ax_speed.plot(d["time_s"], d["speed_mps"], color=COLORS.get(tid, INK), linewidth=1.5)
    _threshold(ax_speed, cfg.DRONE_MIN_SPEED_MPS, f"{cfg.DRONE_MIN_SPEED_MPS:g} m/s — slower is not a drone")
    ax_speed.set_ylim(0, 45)
    ax_speed.set_ylabel("speed (m/s)", color=INK_MUTED)
    ax_speed.set_title("Does it move like a drone?", loc="left", fontsize=10, color=INK)

    # --- fit score ----------------------------------------------------------
    fit_top = 30
    for tid in track_ids:
        d = rows_for(decisions, tid)
        ax_fit.plot(d["time_s"], np.minimum(d["fit_nis"], fit_top), color=COLORS.get(tid, INK), linewidth=1.2)
    _threshold(ax_fit, cfg.MAX_FIT_NIS, f"{cfg.MAX_FIT_NIS:g} — above is not a straight line")
    ax_fit.set_ylim(0, fit_top)
    ax_fit.set_ylabel("fit score (NIS)", color=INK_MUTED)
    ax_fit.set_title(f"Does it fly straight? (clipped at {fit_top})", loc="left", fontsize=10, color=INK)

    # --- how long we may still wait -----------------------------------------
    wait_top = 100
    for tid in track_ids:
        d = rows_for(decisions, tid)
        live = (d["status"] != "launched") & np.isfinite(d["deadline_in_s"])
        wait = np.where(live, np.minimum(d["deadline_in_s"], wait_top), np.nan)
        ax_wait.plot(d["time_s"], wait, color=COLORS.get(tid, INK), linewidth=1.5)
    _threshold(ax_wait, cfg.LAUNCH_LEAD_S, f"{cfg.LAUNCH_LEAD_S:g} s lead — launch when a confirmed threat reaches this")
    ax_wait.set_ylim(0, wait_top)
    ax_wait.set_ylabel("seconds left (s)", color=INK_MUTED)
    ax_wait.set_title(f"How long can we still wait before the intercept falls inside "
                      f"{cfg.PROTECTED_RADIUS_M + cfg.INTERCEPT_MARGIN_M:g} m? "
                      f"(objects that never get close are not drawn)",
                      loc="left", fontsize=10, color=INK)
    ax_wait.set_xlabel("time (s)", color=INK_MUTED)
    ax_wait.set_xlim(0, cfg.SIM_DURATION_S)

    # --- launch moments across every panel ----------------------------------
    for L in launches:
        for ax in axes:
            ax.axvline(L["time_s"], color="#d03b3b", linewidth=1.4)
            ax.axvline(L["intercept_time_s"], color="#d03b3b", linewidth=1.0, linestyle=":")
        ax_ca.annotate(f"LAUNCH at {L['track_id']}, t = {L['time_s']:.1f} s\n"
                       f"meets it at t = {L['intercept_time_s']:.1f} s, {L['intercept_range_m']:.0f} m out\n"
                       f"expected aim error {L['aim_sigma_m']:.1f} m",
                       xy=(L["time_s"], 1350), xytext=(-8, 0), textcoords="offset points",
                       ha="right", va="top", fontsize=8.5, color=INK)

    if title:
        fig.suptitle(title, fontsize=12, color=INK, x=0.06, ha="left")
    fig.savefig(path, dpi=120, facecolor=fig.get_facecolor())
    plt.close(fig)
