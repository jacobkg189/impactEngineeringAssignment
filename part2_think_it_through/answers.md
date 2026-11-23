# Part 2 — Think it through

All numbers are from my own runs (50 seeds per case). Tables: [numbers.md](numbers.md), rerun with `python -m part2_think_it_through.experiments`.

**1. How sure before launching? What does one more second buy and cost?**
The way the code answers on how "sure" it is before launching is through two ways . *Is it a threat?* It must come inside 500 m even if its closest approach
is 2σ worse than estimated and it must also move at drone
speed and fly straight, all for 3 s. A passes this at t ≈ 10 s, 2.75 km out. In 100 runs, B never
got closer than 718 m to the 500 m line, and the bird never went faster than 14.4 m/s, against
18 m/s. The second question is *Will the interceptor reach it?* This is what sets the launch time, because aim error grows with flight time:

| launch | flight | met at | miss mean / worst | hits (15 m reach) |
|---|---|---|---|---|
| at confirmation | 34 s | 1880 m | 25 / 68 m | 11/50 |
| 20 s before deadline | 19 s | 952 m | 5.8 / 13.9 m | 50/50 |
| **5 s before (mine)** | **14 s** | **687 m** | **4.9 / 11.8 m** | **50/50** |
| 1 s later | 14 s | 669 m | 5.1 / 14.8 m | 50/50 |

At my launch point one more second **buys nothing** (miss 4.9 → 5.1 m). It **costs 18 m** and 1 s
of the 10.6 s left before the meeting falls inside 500 m. Waiting only pays while the flight is long.

**2. The radar goes silent for 3 s.**
The tracker coasts on constant velocity, and the track survives. 
After the launch nothing changes: the interceptor flies straight and needs no radar. If the launch falls due during the silence, it goes on the coasted track (last report 1.1 s old, aim error 9.3 instead of 8.8 m, 50/50 hits). **A flaw this exposed:** after the gap, the fit score has too few reports and becomes "unknown", so the 3 s threat clock restarts. If the silence ends just before the launch, the launch slips up to 5.9 s and the meeting moves from 681 m to 585 m. It is still 50/50 outside 500 m, but half the margin is gone. Fix: a gap is not evidence, so keep the verdict while coasting.

**3. Two threats, one interceptor.**
The code queues the threats by urgency: the one with the least time left before it would get inside the zone goes first. It launches at that one earlier than usual, by just enough that the next interceptor (ready 15 s after a launch, my assumption) is in time for the second threat. In 50 runs with two threats arriving at the same moment from different sides, both were met outside 500 m in **50/50** (first 950 m out, second 684 m). Taking the closest one first without launching early is not enough: **0/50**, because the second threat waits for the interceptor and is met 424 m out. If the next interceptor takes 30 s, the first launch moves 30 s earlier, its flight gets longer, and one run in 50 misses.

**4. Where does the human belong?**
On the launch decision. There is time for it: confirmation at t ≈ 10 s, launch at t ≈ 78 s. The
software asks at confirmation. A *yes* arms the launch, and the software still picks the moment.
No *yes* means no launch, with an alarm that escalates toward the deadline. To decide within 5 s,
the operator needs:
**a map** (site, 500 m ring, this track's reports, predicted path and intercept point, other tracks
greyed with one word: "clear", "slow"); **why**, in one line ("passes 7 ± 23 m from the site ·
25 m/s · straight for 70 s"); **the plan** ("meets it 686 m out in 14 s, expected miss 9 m, reach
15 m"); and **the clock and health** (seconds left, last radar report 0.1 s ago, interceptors
ready: 1). All of it is already in the launch record.

**5. What would I measure first on a real radar?**
1. **Position noise, against the 15 m the tracker assumes.** At a real 30 m, A looks "not flying
   straight" and the software **never launches (0/50)**. Silently.
2. **Real bird speeds at the site.** Only the speed test stops the bird. A 20 m/s bird is launched
   at in **11/50** runs.
3. **Latency.** 0.6 s of hidden latency did no harm here only because the engagement is head-on.
   Crossing at 25 m/s, it is 15 m sideways: the whole reach.
4. **How reports go missing.** Random 30% drops are fine (50/50); bursts are not (Q2).
5. **Whether track IDs hold** through crossings and gaps. The software trusts them completely.

The method: fly a GPS-logged drone on known lines, and record birds at the site for days.
