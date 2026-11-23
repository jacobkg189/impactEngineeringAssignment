"""
Run Part 1.4 on its own (needs Parts 1.1-1.3 output for this seed):

    .venv/bin/python -m part1_4_show_it.run --seed 0

Reads   part1_1_generator/output/reports_seed0.csv, truth_seed0.csv   (truth is allowed here: JUDGE side)
        part1_2_tracker/output/estimates_seed0.csv
        part1_3_decision/output/decisions_seed0.csv, launches_seed0.csv
Writes  part1_4_show_it/output/replay_seed0.html    interactive 3D replay: open it in a browser
        part1_4_show_it/output/replay_seed0.png     the same story as one still picture
"""

import argparse

from common import config as cfg
from common.files import read_decisions, read_estimates, read_launches, read_reports, read_truth
from common.paths import (SHOW_IT_OUTPUT, decisions_csv, estimates_csv, launches_csv, reports_csv,
                          truth_csv)
from part1_4_show_it.src.replay import replay_all
from part1_4_show_it.src.scene3d import build_figure, write_html
from part1_4_show_it.src.snapshot import plot_snapshot


def headline(seed, engagements, track_ids):
    """One line: what happened in this run, worked out from the replay, not assumed."""
    parts = []
    for e in engagements:
        if e.contact:
            parts.append(f"{e.track_id} met {e.contact_range_m:.0f} m from the site, closest pass "
                         f"{e.pass_distance_m:.1f} m (reach {cfg.TOUCH_RADIUS_M:g} m)")
        else:
            parts.append(f"interceptor missed {e.track_id} by {e.pass_distance_m:.0f} m")
    quiet = [t for t in track_ids if t not in {e.track_id for e in engagements}]
    if quiet:
        parts.append(f"no launch at {' or '.join(quiet)}")
    return f"Seed {seed} · " + " · ".join(parts)


def run(seed):
    truth = read_truth(truth_csv(seed))
    reports = read_reports(reports_csv(seed))
    estimates = read_estimates(estimates_csv(seed))
    decisions = read_decisions(decisions_csv(seed))
    launches = read_launches(launches_csv(seed))
    engagements = replay_all(launches, truth)
    title = headline(seed, engagements, sorted(set(truth["track_id"])))

    SHOW_IT_OUTPUT.mkdir(parents=True, exist_ok=True)
    page = SHOW_IT_OUTPUT / f"replay_seed{seed}.html"
    png = SHOW_IT_OUTPUT / f"replay_seed{seed}.png"
    fig = build_figure(truth, reports, estimates, decisions, launches, engagements, title=title)
    write_html(fig, page, page_title=f"Replay seed {seed}")
    plot_snapshot(truth, reports, estimates, decisions, launches, engagements, png, title=title)

    print(f"[1.4 show it]   seed {seed}: {len(engagements)} launch(es) replayed against the truth")
    for e in engagements:
        verdict = "CONTACT" if e.contact else "MISS"
        print(f"                {e.track_id}: closest pass {e.pass_distance_m:.1f} m at t = {e.pass_time_s:.1f} s, "
              f"{e.contact_range_m:.0f} m from the site -> {verdict} (reach {cfg.TOUCH_RADIUS_M:g} m)")
        print(f"                  planned: t = {e.expected_time_s:.1f} s, {sum(e.aim ** 2) ** 0.5:.0f} m out; "
              f"aim point off by {e.aim_error_m:.1f} m")
    print(f"                wrote part1_4_show_it/output/{page.name} ({page.stat().st_size / 1e6:.1f} MB, "
          f"open in a browser), {png.name}")
    return engagements


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=0)
    run(parser.parse_args().seed)
