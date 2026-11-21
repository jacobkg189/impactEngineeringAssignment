# Numbers behind answers.md

_Written by `python -m part2_think_it_through.experiments`: seeds 0–49, 50 runs per row. Do not edit by hand._

## Q1 — launching earlier or later

| launch rule | order at t (s) | A really out at order (m) | flight (s) | met at, mean (min) (m) | closest pass mean / max (m) | contact | met outside 500 m |
|---|---|---|---|---|---|---|---|
| at confirmation (earliest) | 10.2 | 2746 | 34.4 | 1880 (1852) | 25.0 / 68.0 | 11/50 | 11/50 |
| lead 40 s | 43.1 | 1924 | 24.7 | 1305 (1288) | 7.1 / 16.1 | 48/50 | 48/50 |
| lead 20 s | 63.1 | 1424 | 18.9 | 952 (942) | 5.8 / 13.9 | 50/50 | 50/50 |
| lead 10 s | 73.1 | 1173 | 15.9 | 775 (765) | 5.0 / 13.8 | 50/50 | 50/50 |
| **lead 5 s (ours)** | 78.2 | 1048 | 14.4 | 687 (681) | 4.9 / 11.8 | 50/50 | 50/50 |
| lead 4 s (one second later) | 79.2 | 1023 | 14.2 | 669 (663) | 5.1 / 14.8 | 50/50 | 50/50 |
| lead 0 s | 83.1 | 923 | 13.0 | 599 (594) | 5.0 / 14.6 | 50/50 | 50/50 |
| lead 0 s, no 100 m margin (latest) | 88.8 | 782 | 11.3 | 499 (493) | 4.2 / 8.2 | 50/50 | 19/50 |

## Q2 — the radar goes silent for 3 s

| outage | launch later than without it, mean / max (s) | threat clock reset | contact | met outside 500 m | closest meeting to the site (m) |
|---|---|---|---|---|---|
| no outage | 0.0 / 0.0 | 0/50 | 50/50 | 50/50 | 681 |
| t 30–33 s (cruise) | 0.0 / 0.0 | 50/50 | 50/50 | 50/50 | 681 |
| t 72–75 s (ends ~3 s before the launch) | 2.5 / 2.9 | 50/50 | 50/50 | 50/50 | 638 |
| t 75–78 s (launch due at the end) | 3.5 / 5.9 | 33/50 | 50/50 | 50/50 | 585 |
| t 77–80 s (launch due inside it) | 0.0 / 0.4 | 0/50 | 50/50 | 50/50 | 681 |
| t 84–87 s (interceptor in flight) | 0.0 / 0.0 | 0/50 | 50/50 | 50/50 | 681 |

## Q5 — the real radar is not what the software assumes

| what is different | met outside 500 m | runs with a launch at B or C | closest pass mean / max (m) | bird's top speed heading in (m/s) |
|---|---|---|---|---|
| radar as assumed | 50/50 | 0/50 | 4.9 / 11.8 | 13.9 |
| noise 30 m, tracker assumes 15 | 0/50 | 0/50 | — / — | 16.4 |
| 0.3 s unknown latency | 50/50 | 0/50 | 4.8 / 11.7 | 13.9 |
| 0.6 s unknown latency | 50/50 | 0/50 | 4.8 / 11.6 | 13.9 |
| 30% of reports dropped, not 10% | 50/50 | 0/50 | 5.6 / 13.2 | 13.9 |
| bird at 16 m/s, not 12 | 50/50 | 0/50 | 4.9 / 11.8 | 17.9 |
| bird at 20 m/s | 50/50 | 11/50 | 4.9 / 11.8 | 21.7 |
