# Part 1.5 results

_Written by `python -m part1_5_checks.run`. Do not edit by hand._

**All 100 runs:** A intercepted outside 500 m in **100 / 100**, a launch at B or C in **0 / 100**, mean intercept **687 m** from the site. With 95% confidence, in this simulated world the success rate is at least 96.3% and the wrong-launch rate at most 3.7%.

### The PDF's 50 runs (seeds 0–49)

| Check (PDF) | Result | 95% interval |
|---|---|---|
| A intercepted outside 500 m | **50 / 50** (100%) | 93–100% |
| runs with a launch at B or C | **0 / 50** (0%) | 0–7% |
| intercept distance from the site | **mean 687 m** (min 681, max 693, sd 2.9) | |

| Behind those numbers | |
|---|---|
| launches at A / contacts | 50 / 50 |
| true closest pass (interceptor to A) | mean 4.9 m, 95th pct 9.4 m, max 11.8 m (reach 15 m; claimed 1σ 8.8 m) |
| launch order | t = 77.8–78.5 s, A really 1039–1057 m out |
| time to spare | contact came 7.5 s (min 7.3 s) before A would have crossed 500 m |
| B's tightest call | closest approach + 2σ never below **718 m** (a launch needs < 500 m) |
| the bird's tightest call | it headed in during 49 of 50 runs (mean 25 s per run); its top speed then was **13.9 m/s** vs the 18 m/s drone test |
| A on the other side of that test | slowest estimated speed while heading in: **23.3 m/s** |
| longest B or C held the threat test | 0.0 s (a launch needs 3 s) |

### Held-out seeds, never used for tuning (seeds 1000–1049)

| Check (PDF) | Result | 95% interval |
|---|---|---|
| A intercepted outside 500 m | **50 / 50** (100%) | 93–100% |
| runs with a launch at B or C | **0 / 50** (0%) | 0–7% |
| intercept distance from the site | **mean 687 m** (min 681, max 693, sd 3.0) | |

| Behind those numbers | |
|---|---|
| launches at A / contacts | 50 / 50 |
| true closest pass (interceptor to A) | mean 4.9 m, 95th pct 8.2 m, max 10.0 m (reach 15 m; claimed 1σ 8.8 m) |
| launch order | t = 77.8–78.5 s, A really 1039–1057 m out |
| time to spare | contact came 7.5 s (min 7.3 s) before A would have crossed 500 m |
| B's tightest call | closest approach + 2σ never below **730 m** (a launch needs < 500 m) |
| the bird's tightest call | it headed in during 49 of 50 runs (mean 26 s per run); its top speed then was **14.4 m/s** vs the 18 m/s drone test |
| A on the other side of that test | slowest estimated speed while heading in: **22.0 m/s** |
| longest B or C held the threat test | 0.0 s (a launch needs 3 s) |
