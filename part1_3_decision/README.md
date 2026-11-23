# Part 1.3 — Decision

> **PDF:** For each object, decide launch or no launch, and when. For a launch, give the
> intercept point and time you expect. The decision code never reads the true paths and
> has no hard coded answers.

**Run:** `.venv/bin/python -m part1_3_decision.run --seed 0` (needs Part 1.2 output)
**Test:** `.venv/bin/pytest part1_3_decision -v`

## What it does
Every 0.1 s, for every track, it gives a verdict and records every number behind it. It reads
the tracker's estimates and nothing else. It never sees the truth or the names A/B/C.
A track becomes a launch only after passing a chain of tests in order. The first test it fails
names its status:

| # | Test | Fails → status | Rules out |
|---|---|---|---|
| 1 | tracked ≥ 5 s and has a fit score | `young` | judging on an unsettled velocity |
| 2 | **heading in:** closest approach + 2σ < 500 m | `clear` | B (passes 700–900 m) |
| 3 | **moves like a drone:** speed ≥ 18 m/s | `slow` | the bird (~12 m/s) |
| 4 | **flies straight:** fit score ≤ 6 | `erratic` | the bird when it turns (backup) |
| 5 | tests 2–4 held 3 s without a break | `threat` (watching) | one-tick blips |
| 6 | an intercept solution exists | `too_late` | — |
| 7 | **time to go:** ≤ 5 s left before the intercept would fall inside 600 m | `confirmed` (holding) → `launch` | — |

**The intercept point** comes from solving where a 60 m/s interceptor, leaving 3 s after the
order, meets a target flying on at its estimated velocity. That is one quadratic, with no
iteration (`geometry.py`). The launch row stores the aim point, the expected intercept time and
range, the expected aim error (1σ), and the numbers that triggered the launch.

### Why launch late on purpose
Once A is confirmed (t = 9.3–10.9 s, A about 2.75 km out), it could be engaged right away. The
meeting would then be about 1.9 km out after a 34–35 s flight (computed over seeds 0–9).
We wait instead:
- **Aim error grows with flight time.** Velocity error × time in the air = miss. A 14 s flight
  needs a short prediction, and a 40 s one doesn't.
- **The target has less time to change its mind** between the order and the intercept.
- **The cost is margin.** So we launch only when 5 s (`LAUNCH_LEAD_S`) remain before the
  intercept would fall inside 500 m + 100 m margin. On seed 0, A is about 1050 m out at the
  order, and we could still have waited **10.5 s** and hit it outside 500 m.
  (Waiting 1 s moves the intercept about 17.6 m closer: 25 × 60 / 85.)

That is a choice, not something the physics forces. Part 2 Q1 discusses it with numbers.
In the review, a slower interceptor makes this same rule launch earlier on its own (tested).

### Why these tests, and not a probability or a classifier
Each test is one sentence an operator can check against the screen ("passing at 7 ± 23 m,
25 m/s, flying straight, for 70 s"). The thresholds sit in `common/config.py` with the
measurement behind each one. A learned classifier would need training data we don't have, and
it couldn't explain itself in the 5 s that Part 2 Q4 asks about.

## Results (seed 0 shown; 50-seed check run here as a sanity pass, Part 1.5 does it properly)
Seed 0: launch at A at t = 78.0 s. The interceptor leaves at 81.0 s and is expected to meet A at
92.4 s, **686 m out**, with an expected aim error of 8.8 m (touch radius 15 m). B and C: no launch.

Over 50 seeds, judged against truth (truth is used only for this check):
- **50/50:** exactly one launch, always at A, and never at B or C.
- B and C **never pass the threat test for even one tick** (the longest any held was 0 s).
- True miss distance, aim point vs where A really was: **mean 6.0 m, 95th pct 10.3 m, max 12.1 m**.
  The claimed 1σ is 8.8 m, so the claim is honest and slightly cautious.
- Intercept happens **678–695 m** from the site. The launch order comes at t = 77.8–78.5 s,
  about 70 s after A was first confirmed.

## What the plot shows (`output/decision_seed0.png`)
Five panels share one time axis, and a red line marks the launch order:
1. **Verdict lanes.** A is young, then threat, then confirmed for about 70 s, then launched.
   B is clear the whole time. The bird is clear, then slow.
2. **Closest approach ± 2σ** against the 500 m line. A sits near 0 m, and B sits at about 780 m
   until it passes.
3. **Speed** against 18 m/s. **4. Fit score** against 6.
5. **Seconds we can still wait.** A's line falls steadily, and the launch fires when it reaches
   the 5 s lead.

**The finding worth discussing:** from t ≈ 85 s to 118 s the bird flies almost straight at the
site, and its closest approach drops to about 50 m. **Only the speed test stops it.** That held
over all 50 seeds: whenever the bird is heading inside 500 m, its top estimated speed is 13.9 m/s,
against a threshold of 18 m/s and A's lowest of 23.3 m/s. The fit score never had to decide
anything (the bird is never `erratic`, because `slow` comes first). Its high value during
that dash is the second layer of defence.
If the review makes the bird faster (say 20 m/s), the fit score is the only thing left. The
tracker README shows that the bird can fly straight enough to look like a drone for 35 s. Fixes:
a slower-to-trust rule for slow-ish objects, an IMM tracker, or radar features beyond position
(size, micro-Doppler).

## More than one threat (added after Part 2 Q3)
The PDF scenario has one threat, and for it nothing above changes: the 100 runs of Part 1.5 are
byte-identical to before this was added. With more than one confirmed threat, a second step
(`Decider._assign`) runs each tick after every track has been judged:

1. **Interceptors are counted.** One is ready at the start, and the next is ready
   `INTERCEPTOR_REARM_S` (15 s) after each launch, until the container (`INTERCEPTORS_IN_CONTAINER`, 4)
   is empty. Both numbers are assumptions.
2. **Most urgent first.** The queue is ordered by the time left before the meeting would fall inside
   600 m. For threats at the same speed, that is the closest one. A farther but faster threat can
   come first (tested).
3. **Make time for the next interceptor.** The first launch moves earlier, but only by as much as
   the next interceptor needs to be ready for the next threat (`MAKE_TIME_FOR_NEXT`).
4. A threat that is due while no interceptor is ready gets the status **`queued`**, and it is
   launched at the moment one is ready.

Measured over 50 seeds, with a second threat (A's own flight, from another side) arriving at the
same moment (`part2_think_it_through/numbers.md`, Q3):

| setting | 1st ordered / met at | 2nd ordered / met at | both met outside 500 m |
|---|---|---|---|
| **as built** (next ready after 15 s, makes time) | t 63.2 s / 950 m | t 78.3 s / 684 m | **50 / 50** |
| closest first only, no making time | t 78.0 s / 689 m | t 93.0 s / 424 m | 0 / 50 |
| next ready after 30 s, makes time | t 48.4 s / 1212 m | t 78.4 s / 682 m | 49 / 50 |
| only one interceptor in the container | t 78.0 s / 689 m | never | 0 / 50 |

Picking the closest one first is not enough on its own: the second threat then waits for the
interceptor and is met 424 m out. Moving the first launch 15 s earlier fixes that at no cost here
(a 19 s flight still touched in 50/50, Part 2 Q1). At 30 s the price shows: the first flight is
22 s long, and one run in 50 misses (worst closest pass 17.2 m, touch radius 15 m).

## Known limits
- **One interceptor per track.** If it misses, nothing re-launches. Doing that needs a check that
  the first one really touched, which isn't in the scenario.
- **The interceptor numbers are assumptions.** The container holds 4, and the next one is ready
  15 s after a launch. Neither is in the PDF.
- If a track is dropped (silent > 5 s) and then reappears under the same id, its age and
  threat-hold carry over from before. That is harmless here, since the radar keeps ids, but a
  real system should reset them.

## src/
| File | Side | What it does |
|---|---|---|
| `geometry.py` | SYSTEM | pure math: closest approach, prediction σ, intercept solve, how long we can wait |
| `decision.py` | SYSTEM | the `Decider`, fed tick by tick: judges every track, then `_assign` gives the queued threats their interceptors; `decide_live()` runs tracker + decider in one real-time loop |
| `plot_decision.py` | SYSTEM | the picture above, drawn from decisions + launches only |

## tests/ (`test_decision.py`, 21 checks)
Geometry against hand-computed cases · over 10 seeds, one launch at A, met outside 500 m and
(judged with truth) inside the touch radius · launch is late on purpose but before the deadline ·
swapping the track names still launches at the threat · a slower interceptor (40 m/s) launches
earlier and still hits · decisions at time t don't change if later data is removed · the live
loop equals the file route · decision code never imports truth · output files round-trip ·
plot draws · **two threats:** adding a second threat leaves A, B and C unchanged · the most urgent
goes first and both are met outside 500 m (3 seeds) · the first launch moves earlier by no more
than the next interceptor needs · without that rule the second waits (`queued`) and is met inside
500 m · no interceptor left means `queued`, never launched · most urgent is not always the closest.

## output/
| File | Contents |
|---|---|
| `decisions_seedN.csv` | every 0.1 s per object: status, age, speed, closest approach ± σ, fit, intercept-if-launched-now, deadline, threat-hold |
| `launches_seedN.csv` | one row per launch order: which interceptor (1, 2, ...), when, aim point, expected intercept time/range, expected aim error, and the numbers behind it |
| `decision_seedN.png` | the plot above |
