"""
scene3d.py — JUDGE side (reads truth). The interactive 3D replay for Part 1.4.

One self-contained HTML page (opens offline, in any browser):

  3D scene    the true path (solid line), radar reports (dots), tracker estimate (dashed),
              the moment the decision step confirmed the threat and the moment it ordered the
              launch (diamonds), its predicted path to the planned intercept point (red dots),
              the interceptor's path, and a moving sphere for every object at the slider's time.
              The interceptor carries a see-through sphere of its reach (the 15 m touch radius).
              The two "touch" when the object is inside that sphere.
  time panel  distance to the site over time, in the same colours, with a time cursor and
              the same moments marked.
  controls    view buttons (whole scene / close-up on the meeting / top-down), a time slider,
              play from the start (it slows down near the meeting so you can watch it).
              The legend has one entry per LAYER (true path, radar reports, tracker
              estimate, launch plan, interceptor), not per object: the colours say which
              object. Click an entry to hide that layer for every object.

Everything is a plain sphere, line or dot on purpose: no models of aircraft or munitions.
Height is stretched in the whole-scene view so the 3 km x 120 m world isn't flat. The
close-up uses true proportions.
"""

import html

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from common import config as cfg
from common.files import positions, rows_for
from common.style import COLORS, NAMES, SURFACE, INK, INK_MUTED, GRID, ZONE
from part1_3_decision.src.plot_decision import STATUS_STYLE
from .replay import (contact_time, first_confirmed_time, latest_row_at, shown_interceptor_position,
                     shown_object_position)

EVENT_RED = "#d03b3b"          # launch order, same red as the 1.3 decision plot
INTERCEPTOR = INK              # ink, not a 4th hue: slot 4 (yellow) clashes with B's orange
Z_ASPECT = 0.28                # height of the 3D box relative to its width (whole-scene view)
CLOSEUP_HALF_M = 70.0          # the close-up box is this many metres either side of the meeting
FRAME_STEP_S = 0.5             # one animation frame per half second...
SLOWMO_STEP_S = 0.1            # ...and every radar tick in the last seconds before a meeting
SLOWMO_BEFORE_S = 4.0
FRAME_MS = 60                  # ms per frame when playing: ~8x real time, slow motion near the meeting
FONT = "Inter, -apple-system, Segoe UI, Helvetica, Arial, sans-serif"


def build_figure(truth, reports, estimates, decisions, launches, engagements, title=""):
    tids = sorted(set(truth["track_id"]))
    stop = {tid: contact_time(engagements, tid) for tid in tids}
    pairs = list(zip(launches, engagements))
    color = {tid: COLORS.get(tid, INK_MUTED) for tid in tids}
    name = {tid: NAMES.get(tid, tid).replace("  ", " ") for tid in tids}

    fig = make_subplots(rows=2, cols=1, specs=[[{"type": "scene"}], [{"type": "xy"}]],
                        row_heights=[0.72, 0.28], vertical_spacing=0.07)

    def add(trace, row):
        fig.add_trace(trace, row=row, col=1)
        return len(fig.data) - 1

    # ---------------------------------------------------------------- scene size ---
    half = np.ceil(np.nanmax(np.abs(positions(truth)[:, :2])) * 1.06 / 100) * 100
    z_top = np.ceil(np.nanmax(truth["z_m"]) * 1.5 / 20) * 20
    stretch = Z_ASPECT * 2 * half / z_top

    # ---------------------------------------------------- protected zone + site ---
    # Drawn as a disc on the ground: every object flies below ~130 m, so the 500 m sphere and
    # its ground circle are the same thing here (and a stretched-height dome would mislead).
    R = cfg.PROTECTED_RADIUS_M
    theta = np.linspace(0, 2 * np.pi, 73)
    rr = np.array([0.0, R])
    add(go.Surface(x=np.outer(rr, np.cos(theta)), y=np.outer(rr, np.sin(theta)), z=np.zeros((2, len(theta))),
                   colorscale=[[0, ZONE], [1, ZONE]], showscale=False, opacity=0.22, hoverinfo="skip",
                   legendgroup="zone", showlegend=False, name="zone"), 1)
    add(go.Scatter3d(x=R * np.cos(theta), y=R * np.sin(theta), z=np.zeros_like(theta), mode="lines",
                     line=dict(color=ZONE, width=4), name=f"{R:g} m protected zone", legendgroup="zone",
                     hoverinfo="skip"), 1)
    add(go.Scatter3d(x=[0], y=[0], z=[0], mode="markers+text", text=["site"], textposition="bottom center",
                     marker=dict(symbol="square", size=5, color=INK), textfont=dict(color=INK_MUTED, size=11),
                     name="site: container + radar", showlegend=False, hovertemplate="site (0, 0, 0)<extra></extra>"), 1)

    # ------------------------------------------- per object: truth, reports, estimate ---
    hover = "%{fullData.name}<br>t %{customdata:.1f} s<br>x %{x:.0f}  y %{y:.0f}  z %{z:.0f} m<extra></extra>"
    hover2d = "%{fullData.name}<br>t %{x:.1f} s<br>%{y:.0f} m from the site<extra></extra>"
    # One legend entry per layer, in neutral ink: the colour already says which object.
    _legend_key(add, "true path", "truth", mode="lines", line=dict(color=INK_MUTED, width=5))
    _legend_key(add, "radar reports", "reports", mode="markers", marker=dict(color=INK_MUTED, size=4, opacity=0.6))
    _legend_key(add, "tracker estimate", "estimate", mode="lines", line=dict(color=INK_MUTED, width=3, dash="dash"))
    for tid in tids:
        c = color[tid]
        tr, rp, es = rows_for(truth, tid), rows_for(reports, tid), rows_for(estimates, tid)
        before = tr["time_s"] <= stop[tid]
        rp = rp[rp["time_s"] <= stop[tid]]
        es = es[es["time_s"] <= stop[tid]]

        _path(add, tr[before], f"{name[tid]} · true path", "truth", hover, hover2d,
              line=dict(color=c, width=5), line2d=dict(color=c, width=2.5))
        if (~before).any():
            _path(add, tr[~before], f"{tid} · true path if it had not been met", "truth", hover, hover2d,
                  line=dict(color=c, width=2, dash="dot"), line2d=dict(color=c, width=1.5, dash="dot"),
                  opacity=0.55)
        _path(add, rp, f"{tid} · radar reports", "reports", hover, hover2d, mode="markers",
              marker=dict(color=c, size=1.5, opacity=0.35), marker2d=dict(color=c, size=3, opacity=0.3))
        _path(add, es, f"{tid} · tracker estimate", "estimate", hover, hover2d,
              line=dict(color=c, width=3, dash="dash"), line2d=dict(color=c, width=1.5, dash="dash"))

    # --------------------------------------------- per launch: the decision moments ---
    if pairs:
        _legend_key(add, "launch plan: order ◆ → aim point", "plan", mode="lines+markers",
                    line=dict(color=EVENT_RED, width=4, dash="dot"), marker=dict(symbol="diamond", size=5, color=EVENT_RED))
        _legend_key(add, f"interceptor, reach {cfg.TOUCH_RADIUS_M:g} m", "interceptor", mode="lines+markers",
                    line=dict(color=INTERCEPTOR, width=4), marker=dict(size=5, color=INTERCEPTOR))
    for L, e in pairs:
        tid, c = e.track_id, color[e.track_id]
        t_conf = first_confirmed_time(decisions, tid)
        est_conf = latest_row_at(estimates, tid, t_conf)
        est_order = latest_row_at(estimates, tid, e.order_time_s)
        p_order = _xyz(est_order)
        marks = [(t_conf, _xyz(est_conf), "diamond-open", INK_MUTED, "confirmed threat")]
        marks.append((e.order_time_s, p_order, "diamond", EVENT_RED, "launch order"))
        for t_mark, p, symbol, mc, label in marks:
            add(go.Scatter3d(x=[p[0]], y=[p[1]], z=[p[2]], mode="markers+text", text=[f"{label} {t_mark:.1f} s"],
                             textposition="top center", textfont=dict(color=INK, size=11),
                             marker=dict(symbol=symbol, size=7, color=mc),
                             name=f"{tid} · {label} (estimated position)", legendgroup="plan", showlegend=False,
                             hovertemplate=(f"{label} at t {t_mark:.1f} s<br>estimated {np.linalg.norm(p):.0f} m "
                                            f"from the site<extra></extra>")), 1)
        add(go.Scatter3d(x=[p_order[0], e.aim[0]], y=[p_order[1], e.aim[1]], z=[p_order[2], e.aim[2]], mode="lines",
                         line=dict(color=EVENT_RED, width=4, dash="dot"), legendgroup="plan", showlegend=False,
                         name=f"{tid} · predicted path at the launch order", hoverinfo="skip"), 1)
        add(go.Scatter3d(x=[e.aim[0]], y=[e.aim[1]], z=[e.aim[2]], mode="markers",
                         marker=dict(symbol="x", size=5, color=EVENT_RED),
                         name=f"{tid} · planned intercept point", legendgroup="plan", showlegend=False,
                         hovertemplate=(f"planned intercept point<br>t {e.expected_time_s:.1f} s, "
                                        f"{np.linalg.norm(e.aim):.0f} m from the site<extra></extra>")), 1)
        t_fly = np.linspace(e.leave_time_s, min(e.pass_time_s, cfg.SIM_DURATION_S), 60)
        flown = shown_interceptor_position(L, e, t_fly)
        add(go.Scatter3d(x=flown[:, 0], y=flown[:, 1], z=flown[:, 2], mode="lines",
                         line=dict(color=INTERCEPTOR, width=4), name="interceptor path", legendgroup="interceptor",
                         showlegend=False, customdata=t_fly, hovertemplate=hover), 1)
        add(go.Scatter(x=t_fly, y=np.linalg.norm(flown, axis=1), mode="lines", line=dict(color=INTERCEPTOR, width=2),
                       name="interceptor path", legendgroup="interceptor", showlegend=False, hovertemplate=hover2d), 2)

    # ------------------------------------------------------------ frame timeline ---
    times = np.arange(0, cfg.SIM_DURATION_S + 1e-9, FRAME_STEP_S)
    extra = []
    for e in engagements:
        extra += [e.order_time_s, e.leave_time_s, e.pass_time_s]
        first_tick = np.ceil((e.pass_time_s - SLOWMO_BEFORE_S) / SLOWMO_STEP_S)    # on the radar's 0.1 s grid
        extra += list(np.arange(first_tick, e.pass_time_s / SLOWMO_STEP_S) * SLOWMO_STEP_S)
    times = np.unique(np.round(np.concatenate([times, extra]), 2))
    times = times[(times >= 0) & (times <= cfg.SIM_DURATION_S)]
    start = min((e.pass_time_s for e in engagements if e.contact), default=times[-1])
    start_i = int(np.argmin(np.abs(times - start)))

    obj = {tid: shown_object_position(truth, tid, times, engagements) for tid in tids}
    icp = [shown_interceptor_position(L, e, times) for L, e in pairs]

    # ---------------------------------------------------------- animated traces ---
    sphere = _unit_sphere()
    i_obj = add(go.Scatter3d(mode="markers+text", textposition="middle right", textfont=dict(color=INK, size=13),
                             marker=dict(size=8, color=[color[t] for t in tids], line=dict(color="white", width=1)),
                             name="objects now (true position)", showlegend=False, hoverinfo="text"), 1)
    i_est = add(go.Scatter3d(mode="markers", marker=dict(size=11, symbol="circle-open", color=[color[t] for t in tids]),
                             name="tracker estimate now", legendgroup="estimate", showlegend=False, hoverinfo="text"), 1)
    i_icp = add(go.Scatter3d(mode="markers", marker=dict(size=7, color=INTERCEPTOR, line=dict(color="white", width=1)),
                             name="interceptor now", legendgroup="interceptor", showlegend=False, hoverinfo="text"), 1)
    i_reach = [add(go.Mesh3d(i=sphere["i"], j=sphere["j"], k=sphere["k"], color=INTERCEPTOR, opacity=0.14,
                             flatshading=False, name=f"interceptor reach ({cfg.TOUCH_RADIUS_M:g} m)",
                             legendgroup="interceptor", showlegend=False, hoverinfo="skip"), 1)
               for n in range(len(pairs))]
    i_touch = add(go.Scatter3d(mode="markers", marker=dict(size=18, symbol="circle-open", color=INK),
                               name="contact", showlegend=False, hoverinfo="text"), 1)
    i_cursor = add(go.Scatter(mode="lines", line=dict(color=INK_MUTED, width=1), showlegend=False, hoverinfo="skip"), 2)
    i_now2d = add(go.Scatter(mode="markers", showlegend=False, hoverinfo="skip",
                             marker=dict(size=9, color=[color[t] for t in tids] + [INTERCEPTOR] * len(pairs),
                                         line=dict(color="white", width=1))), 2)
    animated = [i_obj, i_est, i_icp, *i_reach, i_touch, i_cursor, i_now2d]

    def frame_data(k):
        t = times[k]
        P = np.array([obj[tid][k] for tid in tids])
        E = np.array([_xyz(latest_row_at(estimates, tid, t)) if t <= stop[tid] else [np.nan] * 3 for tid in tids])
        I = np.array([p[k] for p in icp]).reshape(-1, 3)
        touch = [e.meeting_point for e in engagements if e.contact and t >= e.pass_time_s - 1e-6]
        T = np.array(touch).reshape(-1, 3)
        dist = np.linalg.norm(np.vstack([P, I]), axis=1)
        data = [
            go.Scatter3d(x=P[:, 0], y=P[:, 1], z=P[:, 2], text=list(tids),
                         hovertext=[f"{name[x]} at t {t:.1f} s" for x in tids]),
            go.Scatter3d(x=E[:, 0], y=E[:, 1], z=E[:, 2], hovertext=[f"{x} · tracker estimate at t {t:.1f} s" for x in tids]),
            go.Scatter3d(x=I[:, 0], y=I[:, 1], z=I[:, 2], hovertext=[f"interceptor at t {t:.1f} s"] * len(I)),
        ]
        for n, (L, e) in enumerate(pairs):
            ordered = t >= e.order_time_s
            centre = I[n] if ordered else np.zeros(3)
            v = (sphere["v"] * cfg.TOUCH_RADIUS_M + centre).astype(np.float32)   # float32 halves the page size
            data.append(go.Mesh3d(x=v[:, 0], y=v[:, 1], z=v[:, 2], opacity=0.14 if ordered else 0.0))
        data.append(go.Scatter3d(x=T[:, 0], y=T[:, 1], z=T[:, 2],
                                 hovertext=[f"contact {np.linalg.norm(p):.0f} m from the site" for p in T]))
        data.append(go.Scatter(x=[t, t], y=[0, 2 * half]))
        data.append(go.Scatter(x=[t] * len(dist), y=dist))
        return data

    # ------------------------------------------------------------- annotations ---
    events = _events_text(engagements, estimates, decisions, tids, name)
    fig.add_annotation(xref="paper", yref="paper", x=1.0, y=0.65, xanchor="right", width=318, yanchor="top", align="left",
                       text=events, showarrow=False, font=dict(size=11.5, color=INK), bgcolor=SURFACE,
                       bordercolor=GRID, borderwidth=1, borderpad=8)
    # (explicit shapes: plotly's add_hline/add_vline refuse a figure that also holds 3D traces)
    fig.add_shape(type="line", xref="x domain", x0=0, x1=1, yref="y", y0=R, y1=R,
                  line=dict(color=INK_MUTED, width=1.2, dash="dash"))
    fig.add_annotation(xref="x domain", x=0.005, yref="y", y=R, xanchor="left", yanchor="bottom", showarrow=False,
                       text=f"{R:g} m protected", font=dict(size=11, color=INK_MUTED))
    for e in engagements:
        t_conf = first_confirmed_time(decisions, e.track_id)
        for t_mark, style, label in [(t_conf, dict(color=INK_MUTED, dash="dash"), "confirmed"),
                                     (e.order_time_s, dict(color=EVENT_RED), "launch order"),
                                     (e.pass_time_s, dict(color=INK, dash="dot"), "contact" if e.contact else "closest pass")]:
            if np.isfinite(t_mark):
                fig.add_shape(type="line", xref="x", x0=t_mark, x1=t_mark, yref="y domain", y0=0, y1=1,
                              line=dict(width=1.3, **style))
                fig.add_annotation(xref="x", x=t_mark, yref="y domain", y=1, yanchor="bottom", showarrow=False,
                                   xanchor="right" if label == "launch order" else "left",
                                   text=label, font=dict(size=11, color=INK))
    static_notes = list(fig.layout.annotations)

    def status_note(k):
        return dict(xref="paper", yref="paper", x=1.0, y=1.0, xanchor="right", width=318, yanchor="top", align="left",
                    showarrow=False, font=dict(size=12, color=INK), bgcolor="rgba(252,252,251,0.92)",
                    bordercolor=GRID, borderwidth=1, borderpad=8,
                    text=_status_text(times[k], tids, name, color, decisions, pairs, I_at=[p[k] for p in icp],
                                      P_at=[obj[tid][k] for tid in tids]))

    # ------------------------------------------------------------------- frames ---
    for i, d in zip(animated, frame_data(start_i)):        # the page opens on the start frame
        fig.data[i].update({key: val for key, val in d.to_plotly_json().items() if key != "type"})
    fig.frames = [go.Frame(name=_fname(t), data=frame_data(k), traces=animated,
                           layout=dict(annotations=static_notes + [status_note(k)]))
                  for k, t in enumerate(times)]
    fig.layout.annotations = static_notes + [status_note(start_i)]

    # ------------------------------------------------------------------- layout ---
    side = side_azimuth(truth, engagements)
    look = np.array([np.cos(side), np.sin(side)])
    whole = _view(-half, half, -half, half, 0, z_top, Z_ASPECT, eye=(*(0.72 * look), 0.62),
                  z_title=f"height (m), stretched ×{stretch:.0f}")
    top = _view(-half, half, -half, half, 0, z_top, Z_ASPECT, eye=(0, 0, 1.6), up=(0, 1, 0),
                z_title=f"height (m), stretched ×{stretch:.0f}", projection="orthographic")
    views = [("Whole scene", whole), ("Top-down", top)]
    if engagements:
        c = engagements[0].meeting_point
        lo_z = max(c[2] - CLOSEUP_HALF_M, -5.0)
        views.insert(1, (f"Close-up: {engagements[0].track_id} meets the interceptor",
                         _view(c[0] - CLOSEUP_HALF_M, c[0] + CLOSEUP_HALF_M, c[1] - CLOSEUP_HALF_M,
                               c[1] + CLOSEUP_HALF_M, lo_z, lo_z + 2 * CLOSEUP_HALF_M, 1.0, eye=(*(1.05 * look), 0.3),
                               z_title="height (m), true scale")))

    play = dict(frame=dict(duration=FRAME_MS, redraw=True), transition=dict(duration=0), mode="immediate")
    fig.update_layout(
        title=dict(text=_title_text(title), x=0.008, xanchor="left", yref="container", y=1.0, yanchor="top",
                   pad=dict(t=50),
                   font=dict(size=24, color=INK)),
        font=dict(family=FONT, color=INK), paper_bgcolor=SURFACE, plot_bgcolor=SURFACE,
        margin=dict(l=10, r=10, t=116, b=70), uirevision="keep", hovermode="closest",
        legend=dict(x=1.0, xanchor="right", y=0.39, yanchor="top", font=dict(size=12.5),
                    title=dict(text="<b>Layers</b>  (click to hide)", font=dict(size=12, color=INK_MUTED)),
                    bgcolor=SURFACE, bordercolor=GRID, borderwidth=1, itemsizing="constant", tracegroupgap=6),
        scene=dict(domain=dict(x=[0.0, 0.74], y=[0.33, 0.97]),
                   xaxis=dict(_axis("x (m), east"), range=whole["xaxis_range"]),
                   yaxis=dict(_axis("y (m), north"), range=whole["yaxis_range"]),
                   zaxis=dict(_axis(whole["z_title"]), range=whole["zaxis_range"]),
                   aspectmode="manual", aspectratio=whole["aspectratio"], camera=whole["camera"]),
        xaxis=dict(domain=[0.05, 0.74], range=[0, cfg.SIM_DURATION_S], title="time (s)", gridcolor=GRID,
                   zeroline=False, color=INK_MUTED),
        yaxis=dict(domain=[0.0, 0.23], range=[0, 2 * half * 0.55], title="distance to site (m)", gridcolor=GRID,
                   zeroline=False, color=INK_MUTED),
        updatemenus=[
            dict(type="buttons", direction="right", x=0.0, y=0.34, xanchor="left", yanchor="bottom",
                 showactive=True, bgcolor=SURFACE, bordercolor=GRID, font=dict(size=11),
                 buttons=[dict(label=lab, method="relayout", args=[_relayout(v)]) for lab, v in views]),
            dict(type="buttons", direction="right", x=0.0, y=-0.035, xanchor="left", yanchor="top",
                 showactive=False, bgcolor=SURFACE, bordercolor=GRID, font=dict(size=11),
                 buttons=[dict(label="▶ Play from start", method="animate",
                               args=[[_fname(t) for t in times], play]),
                          dict(label="❚❚ Pause", method="animate",
                               args=[[None], dict(frame=dict(duration=0, redraw=False), mode="immediate")])]),
        ],
        sliders=[dict(active=start_i, x=0.2, len=0.54, y=-0.02, yanchor="top", pad=dict(t=0, b=0),
                      ticklen=0, tickwidth=0, font=dict(color="rgba(0,0,0,0)", size=1),
                      bgcolor=GRID, bordercolor=GRID, activebgcolor=INK_MUTED,
                      currentvalue=dict(prefix="t = ", font=dict(size=12, color=INK), xanchor="right"),
                      steps=[dict(label=f"{t:.1f} s", method="animate",
                                  args=[[_fname(t)], dict(play, frame=dict(duration=0, redraw=True))])
                             for t in times])],
    )
    return fig


def write_html(fig, path, page_title):
    """Self-contained page: plotly.js is embedded, so it opens offline."""
    page = fig.to_html(include_plotlyjs=True, full_html=True, auto_play=False,
                       default_width="100%", default_height="100vh",
                       config=dict(responsive=True, displaylogo=False, scrollZoom=True))
    head = (f"<head><title>{html.escape(page_title)}</title>"
            f"<style>html,body{{margin:0;background:{SURFACE};}}</style>")
    path.write_text(page.replace("<head>", head, 1), encoding="utf-8")


def side_azimuth(truth, engagements):
    """Camera direction (radians, in the x-y plane): look obliquely across the engaged object's
    approach, 60 deg off it, so it and the interceptor cross the screen instead of coming at the
    viewer. With no launch, look from the south-east."""
    if not engagements:
        return -np.pi / 4
    first = positions(rows_for(truth, engagements[0].track_id))[0]
    return float(np.arctan2(first[1], first[0]) - np.radians(60))


# ------------------------------------------------------------------- helpers ---
def _path(add, rows, label, group, hover, hover2d, mode="lines", line=None, line2d=None,
          marker=None, marker2d=None, opacity=1.0):
    """The same rows twice: as a 3D path, and as distance-to-site over time below it."""
    if len(rows) == 0:
        return
    p = positions(rows).astype(np.float32)
    add(go.Scatter3d(x=p[:, 0], y=p[:, 1], z=p[:, 2], mode=mode, line=line, marker=marker, opacity=opacity,
                     name=label, legendgroup=group, showlegend=False, customdata=rows["time_s"].astype(np.float32),
                     hovertemplate=hover), 1)
    add(go.Scatter(x=rows["time_s"].astype(np.float32), y=np.linalg.norm(p, axis=1), mode=mode, line=line2d, marker=marker2d,
                   opacity=opacity, name=label, legendgroup=group, showlegend=False, hovertemplate=hover2d), 2)


def _legend_key(add, label, group, **style):
    """A legend-only entry (no data). Clicking it hides every trace in `group`."""
    add(go.Scatter3d(x=[None], y=[None], z=[None], name=label, legendgroup=group, hoverinfo="skip", **style), 1)


def _title_text(title):
    """Headline big and bold, the rest of the line smaller underneath."""
    head, _, rest = title.partition(" · ")
    if not rest:
        return f"<b>{head}</b>"
    return f"<b>{head} · interceptor replay</b><br><span style='font-size:14px;color:{INK_MUTED}'>{rest}</span>"


def _pos_line(mark, label, p):
    """One row of the 'position now' table: fixed-width numbers so the columns line up."""
    nums = "       —       —      —" if np.any(np.isnan(p)) else f"{p[0]:8.0f}{p[1]:8.0f}{p[2]:7.0f}"
    return f"{mark} <span style='font-family:Menlo,Consolas,monospace;font-size:11px'>{label:<12}{nums}</span>"


def _xyz(row):
    if row is None:
        return np.full(3, np.nan)
    return np.array([row["x_m"], row["y_m"], row["z_m"]], dtype=float)


def _fname(t):
    return f"{t:.2f}"


def _unit_sphere(n_lat=8, n_lon=14):
    """Vertices and triangles of a unit sphere, for the interceptor's reach."""
    lat = np.linspace(0, np.pi, n_lat)
    lon = np.linspace(0, 2 * np.pi, n_lon, endpoint=False)
    v = np.array([[np.sin(a) * np.cos(b), np.sin(a) * np.sin(b), np.cos(a)] for a in lat for b in lon])
    i, j, k = [], [], []
    for a in range(n_lat - 1):
        for b in range(n_lon):
            p, q = a * n_lon + b, a * n_lon + (b + 1) % n_lon
            r, s = p + n_lon, q + n_lon
            i += [p, q]
            j += [r, r]
            k += [q, s]
    return dict(v=v, i=i, j=j, k=k)


def _axis(title):
    return dict(title=dict(text=title, font=dict(size=11, color=INK_MUTED)), backgroundcolor=SURFACE,
                gridcolor=GRID, zerolinecolor=GRID, showbackground=True, tickfont=dict(size=10, color=INK_MUTED),
                showspikes=False)


def _view(x0, x1, y0, y1, z0, z1, z_aspect, eye, z_title, up=(0, 0, 1), projection="perspective"):
    span = x1 - x0
    return dict(z_title=z_title, xaxis_range=[x0, x1], yaxis_range=[y0, y1], zaxis_range=[z0, z1],
                aspectmode="manual", aspectratio=dict(x=1, y=(y1 - y0) / span, z=z_aspect),
                camera=dict(eye=dict(zip("xyz", map(float, eye))), up=dict(zip("xyz", up)),
                            center=dict(x=0, y=0, z=0), projection=dict(type=projection)))


def _relayout(view):
    return {"scene.xaxis.range": view["xaxis_range"], "scene.yaxis.range": view["yaxis_range"],
            "scene.zaxis.range": view["zaxis_range"], "scene.aspectmode": "manual",
            "scene.aspectratio": view["aspectratio"], "scene.camera": view["camera"],
            "scene.zaxis.title.text": view["z_title"]}


def _status_text(t, tids, name, color, decisions, pairs, I_at, P_at):
    lines = [f"<b>t = {t:.1f} s</b>"]
    met = {e.track_id: e for _, e in pairs if e.contact and t >= e.pass_time_s - 1e-6}
    for tid in tids:
        if tid in met:
            what = f"met by the interceptor {met[tid].contact_range_m:.0f} m from the site"
        else:
            d = latest_row_at(decisions, tid, t)
            what = "not tracked" if d is None else STATUS_STYLE.get(str(d["status"]), (None, str(d["status"])))[1]
        lines.append(f"<span style='color:{color[tid]}'>●</span> {name[tid]}: {what}")
    if not pairs:
        lines.append("■ interceptor: in the container, no launch")
    for (L, e), p in zip(pairs, I_at):
        if t < e.order_time_s:
            what = "in the container"
        elif t < e.leave_time_s:
            what = f"ordered at {e.order_time_s:.1f} s, leaves in {e.leave_time_s - t:.1f} s"
        elif t < e.pass_time_s - 1e-6:
            what = f"flying, {np.linalg.norm(p):.0f} m out, meets {e.track_id} in {e.pass_time_s - t:.1f} s"
        elif e.contact:
            what = (f"touched {e.track_id}: closest pass {e.pass_distance_m:.1f} m "
                    f"(reach {cfg.TOUCH_RADIUS_M:g} m)")
        else:
            what = f"missed {e.track_id} by {e.pass_distance_m:.0f} m (reach {cfg.TOUCH_RADIUS_M:g} m)"
        lines.append(f"■ interceptor: {what}")
    lines.append("")
    lines.append("<span style='font-family:Menlo,Consolas,monospace;font-size:11px'>"
                 f"<b>{'position now':<14}</b>{'x (m)':>8}{'y (m)':>8}{'z (m)':>7}</span>")
    for tid, p in zip(tids, P_at):
        lines.append(_pos_line(f"<span style='color:{color[tid]}'>●</span>", name[tid], np.asarray(p, dtype=float)))
    for p in I_at:
        lines.append(_pos_line("■", "interceptor", np.asarray(p, dtype=float)))
    return "<br>".join(lines)


def _events_text(engagements, estimates, decisions, tids, name):
    lines = ["<b>What happened</b>"]
    for e in engagements:
        tid = e.track_id
        t_conf = first_confirmed_time(decisions, tid)
        if np.isfinite(t_conf):
            r = np.linalg.norm(_xyz(latest_row_at(estimates, tid, t_conf)))
            lines.append(f"t {t_conf:5.1f} s  {tid} confirmed as a threat, {r / 1000:.1f} km out")
        r = np.linalg.norm(_xyz(latest_row_at(estimates, tid, e.order_time_s)))
        lines.append(f"t {e.order_time_s:5.1f} s  <b>launch order</b>, {tid} {r:.0f} m out")
        lines.append(f"t {e.leave_time_s:5.1f} s  interceptor leaves the container")
        if e.contact:
            lines.append(f"t {e.pass_time_s:5.1f} s  <b>contact {e.contact_range_m:.0f} m from the site</b>")
        else:
            lines.append(f"t {e.pass_time_s:5.1f} s  <b>missed</b> {tid}")
        lines.append(f"closest pass {e.pass_distance_m:.1f} m · reach {cfg.TOUCH_RADIUS_M:g} m")
        lines.append(f"planned: t {e.expected_time_s:.1f} s, {np.linalg.norm(e.aim):.0f} m out, "
                     f"aim off by {e.aim_error_m:.1f} m")
    quiet = [t for t in tids if t not in {e.track_id for e in engagements}]
    if quiet:
        lines.append(f"no launch at {', '.join(quiet)}")
    return "<br>".join(lines)
