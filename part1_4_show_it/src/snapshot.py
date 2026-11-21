"""
snapshot.py — JUDGE side (reads truth). The same story as the 3D page, as one still picture
for the README (GitHub can't show the interactive page).

  left    3D, the whole scene at the moment of contact: true paths, reports, estimates, where
          the threat was confirmed and where the launch was ordered, the predicted path to the
          planned intercept point, and the interceptor's path. Height stretched like the page.
  right   3D close-up of the meeting, at true scale: only the engaged object and the
          interceptor, with the interceptor's 15 m reach drawn as a sphere around it.
  bottom  distance to the site over time with the same moments marked.

Plain spheres, lines and dots only, the same as the page.
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import numpy as np

from common import config as cfg
from common.files import positions, rows_for
from common.style import COLORS, NAMES, SURFACE, INK, INK_MUTED, GRID, ZONE, style_axes
from .replay import (contact_time, first_confirmed_time, latest_row_at, shown_interceptor_position,
                     shown_object_position, true_position)
from .scene3d import CLOSEUP_HALF_M, EVENT_RED, INTERCEPTOR, Z_ASPECT, side_azimuth


def plot_snapshot(truth, reports, estimates, decisions, launches, engagements, path, title=""):
    tids = sorted(set(truth["track_id"]))
    stop = {tid: contact_time(engagements, tid) for tid in tids}
    color = {tid: COLORS.get(tid, INK_MUTED) for tid in tids}
    pairs = list(zip(launches, engagements))
    moment = min((e.pass_time_s for e in engagements), default=cfg.SIM_DURATION_S)

    fig = plt.figure(figsize=(16, 10.5))
    fig.patch.set_facecolor(SURFACE)
    ax3 = fig.add_axes([-0.04, 0.33, 0.62, 0.62], projection="3d")
    axz = fig.add_axes([0.53, 0.33, 0.47, 0.62], projection="3d")
    ax2 = fig.add_axes([0.05, 0.06, 0.68, 0.23])

    # ---------------------------------------------------------- whole scene, 3D ---
    half = np.ceil(np.nanmax(np.abs(positions(truth)[:, :2])) * 1.06 / 100) * 100
    z_top = np.ceil(np.nanmax(truth["z_m"]) * 1.5 / 20) * 20
    stretch = Z_ASPECT * 2 * half / z_top
    _style3d(ax3)
    theta = np.linspace(0, 2 * np.pi, 120)
    R = cfg.PROTECTED_RADIUS_M
    ring = np.column_stack([R * np.cos(theta), R * np.sin(theta), np.zeros_like(theta)])
    ax3.add_collection3d(Poly3DCollection([ring], facecolor=ZONE, alpha=0.25, edgecolor=ZONE))
    ax3.scatter([0], [0], [0], marker="s", s=30, color=INK, depthshade=False)
    for tid in tids:
        c, tr = color[tid], rows_for(truth, tid)
        rp = rows_for(reports, tid)
        es = rows_for(estimates, tid)
        before = tr["time_s"] <= stop[tid]
        p = positions(tr)
        ax3.plot(*p[before].T, color=c, lw=2.2)
        ax3.plot(*p[~before].T, color=c, lw=1, ls=":", alpha=0.6)
        q = positions(rp[rp["time_s"] <= stop[tid]])
        ax3.scatter(*q.T, s=0.6, color=c, alpha=0.25, depthshade=False, linewidths=0)
        ax3.plot(*positions(es[es["time_s"] <= stop[tid]]).T, color=c, lw=1, ls="--")
        now = shown_object_position(truth, tid, moment, engagements)[0]
        ax3.scatter(*now, s=70, color=c, edgecolor="white", linewidths=1, depthshade=False, zorder=5)
        ax3.text(*(now + [0, 0, 18]), f" {tid}", fontsize=11, color=INK, fontweight="bold")
    for L, e in pairs:
        t_conf = first_confirmed_time(decisions, e.track_id)
        p_conf = _xyz(latest_row_at(estimates, e.track_id, t_conf))
        p_order = _xyz(latest_row_at(estimates, e.track_id, e.order_time_s))
        ax3.scatter(*p_conf, marker="D", s=40, facecolor="none", edgecolor=INK_MUTED, depthshade=False)
        ax3.text(*(p_conf + [0, 0, 22]), f"confirmed {t_conf:.1f} s", fontsize=9, color=INK, ha="center")
        ax3.scatter(*p_order, marker="D", s=45, color=EVENT_RED, depthshade=False)
        ax3.text(*(p_order - [0, 0, 22]), f"launch order {e.order_time_s:.1f} s", fontsize=9, color=INK,
                 ha="left", va="top")
        ax3.plot(*np.column_stack([p_order, e.aim]), color=EVENT_RED, lw=1.5, ls=":")
        flown = shown_interceptor_position(L, e, np.linspace(e.leave_time_s, e.pass_time_s, 50))
        ax3.plot(*flown.T, color=INTERCEPTOR, lw=2)
        ax3.scatter(*flown[-1], s=40, color=INTERCEPTOR, depthshade=False, zorder=6)
        if e.contact:
            ax3.scatter(*e.meeting_point, s=260, facecolor="none", edgecolor=INK, linewidths=1.3, depthshade=False)
            ax3.text(*(e.meeting_point - [0, 0, 30]), f"contact {e.contact_range_m:.0f} m out",
                     fontsize=9, color=INK, ha="center", va="top")
    ax3.set_xlim(-half, half)
    ax3.set_ylim(-half, half)
    ax3.set_zlim(0, z_top)
    ax3.set_box_aspect((1, 1, Z_ASPECT * 1.6), zoom=1.15)
    side = side_azimuth(truth, engagements)            # same camera direction as the 3D page
    ax3.view_init(elev=30, azim=np.degrees(side))
    ax3.set_xlabel("x (m), east", color=INK_MUTED, fontsize=9)
    ax3.set_ylabel("y (m), north", color=INK_MUTED, fontsize=9)
    ax3.set_zlabel(f"height (m)\nstretched ×{stretch * 1.6:.0f}", color=INK_MUTED, fontsize=9)
    ax3.set_title(f"The whole scene at t = {moment:.1f} s", loc="left", fontsize=11, color=INK, y=0.93)

    # ------------------------------------------------------------ close-up, 3D ---
    _style3d(axz)
    if pairs:
        L, e = pairs[0]
        c, tid = color[e.track_id], e.track_id
        mid = e.meeting_point
        H = CLOSEUP_HALF_M * 0.6
        lo = mid - H
        tr = rows_for(truth, tid)
        tr = tr[tr["time_s"] <= e.pass_time_s]
        es = rows_for(estimates, tid)
        es = es[es["time_s"] <= e.pass_time_s]
        rp = rows_for(reports, tid)
        rp = rp[rp["time_s"] <= e.pass_time_s]
        p_order = _xyz(latest_row_at(estimates, tid, e.order_time_s))
        clip = dict(axlim_clip=True)
        axz.plot(*positions(tr).T, color=c, lw=2.5, label="true path", **clip)
        axz.plot(*positions(es).T, color=c, lw=1.2, ls="--", label="tracker estimate", **clip)
        q = positions(rp)
        near = np.all(np.abs(q - mid) <= H, axis=1)
        axz.scatter(*q[near].T, s=8, color=c, alpha=0.5, depthshade=False, label="radar reports")
        line = np.linspace(p_order, e.aim, 400)
        axz.plot(*line.T, color=EVENT_RED, lw=1.5, ls=":", label="predicted at the launch order", **clip)
        flown = shown_interceptor_position(L, e, np.linspace(e.leave_time_s, e.pass_time_s, 400))
        axz.plot(*flown.T, color=INTERCEPTOR, lw=2, label="interceptor path", **clip)
        axz.scatter(*e.aim, marker="x", s=60, color=EVENT_RED, depthshade=False, label="planned intercept point")
        axz.scatter(*e.object_at_pass, s=110, color=c, edgecolor="white", depthshade=False, zorder=6)
        axz.scatter(*e.interceptor_at_pass, s=60, color=INTERCEPTOR, edgecolor="white", depthshade=False, zorder=6)
        u, v = np.mgrid[0:2 * np.pi:28j, 0:np.pi:15j]
        r = cfg.KILL_RADIUS_M
        axz.plot_wireframe(e.interceptor_at_pass[0] + r * np.cos(u) * np.sin(v),
                           e.interceptor_at_pass[1] + r * np.sin(u) * np.sin(v),
                           e.interceptor_at_pass[2] + r * np.cos(v), color=INK_MUTED, lw=0.4, alpha=0.6)
        axz.text(*(e.object_at_pass + [0, 0, r + 4]), f"{tid}", fontsize=12, fontweight="bold", color=INK)
        axz.set_xlim(lo[0], lo[0] + 2 * H)
        axz.set_ylim(lo[1], lo[1] + 2 * H)
        axz.set_zlim(lo[2], lo[2] + 2 * H)
        axz.set_box_aspect((1, 1, 1), zoom=0.95)
        axz.view_init(elev=18, azim=np.degrees(side))
        axz.set_xlabel("x (m)", color=INK_MUTED, fontsize=9)
        axz.set_ylabel("y (m)", color=INK_MUTED, fontsize=9)
        axz.set_zlabel("height (m), true scale", color=INK_MUTED, fontsize=9)
        verdict = "inside" if e.contact else "outside"
        axz.set_title(f"Close-up of the meeting, t = {e.pass_time_s:.1f} s ({tid} and the interceptor only)\n"
                      f"{tid} passes {e.pass_distance_m:.1f} m from the interceptor: {verdict} its "
                      f"{cfg.KILL_RADIUS_M:g} m reach (grey sphere)",
                      loc="left", fontsize=11, color=INK, y=0.93)
        axz.legend(loc="upper left", fontsize=8.5, frameon=False, bbox_to_anchor=(0.0, 0.86))
    else:
        axz.set_axis_off()
        axz.text2D(0.5, 0.5, "No launch: nothing to show up close", ha="center", transform=axz.transAxes)

    # ------------------------------------------------- distance to site over time ---
    style_axes(ax2)
    for tid in tids:
        c, tr = color[tid], rows_for(truth, tid)
        rp, es = rows_for(reports, tid), rows_for(estimates, tid)
        before = tr["time_s"] <= stop[tid]
        rng = np.linalg.norm(positions(tr), axis=1)
        ax2.plot(tr["time_s"][before], rng[before], color=c, lw=2, label=NAMES.get(tid, tid).replace("  ", " "))
        ax2.plot(tr["time_s"][~before], rng[~before], color=c, lw=1, ls=":", alpha=0.6)
        rp = rp[rp["time_s"] <= stop[tid]]
        ax2.scatter(rp["time_s"], np.linalg.norm(positions(rp), axis=1), s=2, color=c, alpha=0.25, linewidths=0)
        es = es[es["time_s"] <= stop[tid]]
        ax2.plot(es["time_s"], np.linalg.norm(positions(es), axis=1), color=c, lw=1, ls="--")
    ax2.axhline(R, color=INK_MUTED, lw=1.2, ls="--")
    ax2.text(1, R, f"{R:g} m protected", fontsize=8.5, color=INK_MUTED, va="bottom")
    for L, e in pairs:
        t_fly = np.linspace(e.leave_time_s, e.pass_time_s, 50)
        ax2.plot(t_fly, np.linalg.norm(shown_interceptor_position(L, e, t_fly), axis=1), color=INTERCEPTOR, lw=2,
                 label="interceptor")
        t_conf = first_confirmed_time(decisions, e.track_id)
        for t_mark, style, text, ha in [(t_conf, dict(color=INK_MUTED, ls="--"), "confirmed", "left"),
                                        (e.order_time_s, dict(color=EVENT_RED), "launch order", "right"),
                                        (e.pass_time_s, dict(color=INK, ls=":"), "contact" if e.contact else "closest pass", "left")]:
            ax2.axvline(t_mark, lw=1.3, **style)
            ax2.text(t_mark + (0.8 if ha == "left" else -0.8), 2 * half * 0.53, text, ha=ha, va="top",
                     fontsize=9, color=INK)
    ax2.set_xlim(0, cfg.SIM_DURATION_S)
    ax2.set_ylim(0, 2 * half * 0.55)
    ax2.set_xlabel("time (s)", color=INK_MUTED)
    ax2.set_ylabel("distance to site (m)", color=INK_MUTED)
    ax2.set_title("Distance to the site over time", loc="left", fontsize=11, color=INK)
    ax2.legend(loc="upper right", fontsize=8.5, frameon=False, ncol=1)

    # ------------------------------------------------------------- how to read ---
    key = [Line2D([], [], color=INK_MUTED, lw=2.2, label="true path (solid)"),
           Line2D([], [], color=INK_MUTED, lw=0, marker=".", markersize=5, label="radar reports (dots)"),
           Line2D([], [], color=INK_MUTED, lw=1, ls="--", label="tracker estimate (dashed)"),
           Line2D([], [], color=INK_MUTED, lw=1, ls=":", label="true path after contact (not flown)"),
           Line2D([], [], color=INK_MUTED, lw=0, marker="D", markerfacecolor="none", label="threat confirmed"),
           Line2D([], [], color=EVENT_RED, lw=0, marker="D", label="launch order (decided)"),
           Line2D([], [], color=EVENT_RED, lw=1.5, ls=":", label="predicted path at the order"),
           Line2D([], [], color=INTERCEPTOR, lw=2, label="interceptor"),
           Line2D([], [], color=INK, lw=0, marker="o", markerfacecolor="none", markersize=12, label="contact")]
    fig.legend(handles=key, loc="lower left", bbox_to_anchor=(0.765, 0.05), fontsize=9, frameon=False,
               title="How to read it", title_fontsize=10, alignment="left")

    if title:
        fig.suptitle(title, fontsize=13, color=INK, x=0.02, y=0.985, ha="left")
    fig.savefig(path, dpi=110, facecolor=fig.get_facecolor())
    plt.close(fig)


def _xyz(row):
    if row is None:
        return np.full(3, np.nan)
    return np.array([row["x_m"], row["y_m"], row["z_m"]], dtype=float)


def _style3d(ax):
    ax.set_facecolor(SURFACE)
    for axis in (ax.xaxis, ax.yaxis, ax.zaxis):
        axis.set_pane_color((0.99, 0.99, 0.985, 1.0))
        axis._axinfo["grid"]["color"] = GRID
        axis.set_tick_params(labelsize=8, colors=INK_MUTED)
