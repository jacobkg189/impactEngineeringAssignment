# Radar track → launch decision

## Run it
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python run.py          # runs every part in order for seed 0
.venv/bin/pytest                 # all checks
```

## Layout — folders follow the assignment PDF
Every part folder has the same shape: `README.md` (what the PDF asks + how to run),
`src/` (code), `tests/` (checks), `output/` (what it created).

| Folder | PDF section | Status |
|---|---|---|
| `part1_1_generator/` | 1.1 Generator | ✅ done |
| `part1_2_tracker/` | 1.2 Tracker | ✅ done |
| `part1_3_decision/` | 1.3 Decision | ✅ done |
| `part1_4_show_it/` | 1.4 Show it | ✅ done: open `part1_4_show_it/output/replay_seed0.html` |
| `part1_5_checks/` | 1.5 Checks (50 seeds) | ✅ done (results below) |
| `part2_think_it_through/` | Part 2 write-up | ✅ drafted: `answers.md`, numbers from `experiments.py` → `numbers.md` |
| `how_you_work/` | Where Claude was used | ongoing |
| `common/` | shared: `config.py` (every number), `files.py` (CSV formats), `paths.py`, `style.py` | |

## The one rule that shapes the code
The decision code never sees the truth. Only the radar reports flow forward:
```
1.1 generator ──reports.csv──► 1.2 tracker ──estimates──► 1.3 decision ──launches──►
                 truth.csv ─────────────────────────────► 1.4 show it / 1.5 checks (judge only)
```
1.4 draws the true path, reports, estimate, the decision moments and the intercept point as plain
spheres and lines in an interactive 3D page (`part1_4_show_it/output/replay_seed0.html`).

## Assumptions
See `common/config.py` (every value tagged `[PDF]`, `[ASSUMPTION]` or `[TUNING]`) and each part's README.

## Results
Part 1.5: the whole chain, scored against the truth, over the PDF's 50 seeds plus 50 held-out
seeds that no tuning step ever saw. Details and the picture are in `part1_5_checks/README.md`.

| | seeds 0–49 | held-out 1000–1049 |
|---|---|---|
| **A intercepted outside 500 m** | **50 / 50** | **50 / 50** |
| **runs with a launch at B or C** | **0 / 50** | **0 / 50** |
| **mean intercept distance from the site** | **687 m** (681–693) | **687 m** (681–693) |
| true closest pass, interceptor to A (touch radius 15 m) | mean 4.9 m, max 11.8 m | mean 4.9 m, max 10.0 m |

- 100/100 means a **≥ 96.3%** success rate with 95% confidence, *in this simulator*.
- Every intercept is ~687 m **by design**: launch 5 s before the meeting would fall inside 600 m,
  and 600 + 5 × 17.6 m/s ≈ 688 m. B and the bird never start the threat clock, so they can't move it.
- **The weak spot is the bird.** It heads at the site in 98/100 runs, and only the speed test stops
  it: its worst is 14.4 m/s against an 18 m/s threshold.
- Seed 0, replayed in 3D: `part1_4_show_it/output/replay_seed0.html`.

## Time spent
_TODO_

## What I'd do next
_TODO_
