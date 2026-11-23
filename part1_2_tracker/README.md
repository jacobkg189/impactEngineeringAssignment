# Part 1.2 — Tracker

> **PDF:** From the reports alone, estimate where each object is and where it is going.
> Pick your own method and tell us why you picked it.

**Run:** `.venv/bin/python -m part1_2_tracker.run --seed 0` (needs Part 1.1 output)
**Test:** `.venv/bin/pytest part1_2_tracker -v`
**Re-tune:** `.venv/bin/python -m part1_2_tracker.src.tune`

## Method: constant-velocity Kalman filter, one per object, in 3D — and why
The radar only gives positions, each off by 15 m. Velocity must be inferred, and it matters
most: the interceptor aims ~15 s ahead, so velocity error × 15 s = aim error.

| Way to get velocity | Error (1σ) |
|---|---|
| difference of 2 reports, 0.1 s apart | 216 m/s |
| best-fit line over last 5 s | 1.5 m/s |
| best-fit line over last 10 s | 0.53 m/s |

A Kalman filter is the recursive form of that best-fit line (our test proves they're equal when
q = 0), with three extras we need:
1. **Missing reports are free** — no report, just predict; uncertainty grows honestly.
2. **It says how sure it is** (covariance) — the decision step needs that.
3. **One knob, q, sets the memory** — the speed-vs-accuracy trade-off is explicit and tunable.

Considered and not chosen: moving average (lags, no uncertainty), alpha-beta (no uncertainty),
IMM / multiple models (the professional answer for drone-vs-bird, too much for the time box —
listed under next steps), particle filter (more than this needs), ML (no data).

## Choosing q (`output/tuning.txt`, 20 seeds)
| q | A velocity RMS | A 15 s aim RMS | bird: filter overconfident by | bird fit score |
|---|---|---|---|---|
| 0.001 | 0.22 m/s | 6 m | 20× | 17 |
| **0.01 (chosen)** | **0.32 m/s** | **8 m** | **10×** | **9** |
| 0.1 | 0.66 m/s | 14 m | 4× | 5 |
| 1 | 1.56 m/s | 29 m | 2× | 3.4 |

Long memory aims well at straight flyers but is badly overconfident about the bird. So we
don't trust the filter's confidence alone — we add a **fit score**.

## Fit score (NIS)
Every report, the filter measures how surprised it was, in units of what it expected (NIS).
A true straight flyer averages **3**. Averaged over 5 s: A and B median 3.0 (max 4.5 over
20 seeds); the bird median 9, often > 20. The decision step can use this to say
"this doesn't fly like a drone on a straight line".

## src/
| File | Side | What it does |
|---|---|---|
| `kalman.py` | SYSTEM | the filter for one object: predict, update, uncertainty, NIS |
| `tracker.py` | SYSTEM | one filter per track_id, fed tick by tick (real time); drops tracks silent > 5 s |
| `compare.py` | JUDGE | grades estimates against truth (tests, tuning, plot only) |
| `tune.py` | JUDGE | tries several q values over 20 seeds |
| `plot_tracker.py` | JUDGE | speed, error (actual vs claimed), fit score — per object |

## tests/ (`test_tracker.py`)
q=0 filter equals best-fit line · uncertainty grows in a 3 s gap and shrinks after ·
velocity < 0.5 m/s and 15 s aim < 15 m on A and B · claimed error matches actual ·
fit score separates bird · estimate at time t identical with or without later reports ·
coasts through 3 s gap, drops after 5 s · tracker code never imports truth.

## output/
| File | Contents |
|---|---|
| `estimates_seedN.csv` | every 0.1 s per object: position, velocity, claimed errors, report count, staleness, fit score |
| `tracker_seedN.png` | how good the tracker was on that seed |
| `tuning.txt` | the q comparison table |

## What the plot shows (seed 0)
- A and B: speed locks on within ~10 s; actual error ~3 m sits just under the claimed ~4 m.
- Bird: when it turns, the long-memory estimate lags (speed dips toward 0, error up to 80 m
  while the filter still claims 4 m) — and the fit score jumps to 10–30, flagging exactly that.
- **Caveat for the decision step:** for its first ~35 s the bird happened to fly fairly straight
  and its fit score sat near 3. Fit alone can't rule out a bird; **speed** (≈12 vs 25–30 m/s)
  and **where it's heading** must be combined with it.
