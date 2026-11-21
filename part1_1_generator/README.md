# Part 1.1 — Generator

> **PDF:** Write the radar reports for the three objects to a file, with the noise and the
> missing reports. Keep the true paths in a separate file.

**Run:** `.venv/bin/python -m part1_1_generator.run --seed 0`
**Test:** `.venv/bin/pytest part1_1_generator -v`

## src/ — the code, in the order data flows through it
| File | What it does |
|---|---|
| `scenario.py` | Builds the TRUE paths of A (threat), B (passer), C (bird), one row every 0.1 s |
| `radar.py` | Turns truth into radar reports: 15 m noise per axis, ~10% dropped, positions only |
| `generator.py` | Glue: seed → truth → reports → two CSV files |
| `plot_world.py` | Picture to check the generated world looks like the PDF describes |

## tests/
`test_generator.py` — one test per claim in the PDF (drop rate, noise level, A flies
straight at the site at 25 m/s, B never within 700 m, bird stays near 900 m and sometimes
dashes at the site, same seed = same data, files read back identical).

## output/ — what it created
| File | Contents | Who may read it |
|---|---|---|
| `reports_seedN.csv` | `track_id, time_s, x_m, y_m, z_m` | everyone (this is the radar feed) |
| `truth_seedN.csv` | same + true velocity | **only** the checking/plotting code, never tracker or decision |
| `world_seedN.png` | map + distance-over-time plot | you |

## Assumptions made here (all in `common/config.py`)
- A starts 3 km out horizontally at 100 m altitude, random bearing, flies a straight 3D line to (0,0,0).
- B's closest approach is 700–900 m, reached between t = 40 and 90 s, at 120 m altitude.
- C wanders at 12 m/s near the 900 m ring; ~5%/s chance of a 3–6 s dash straight at the site.
- Radar noise is independent on x, y, z; drops are independent and random.
