"""
config.py — every number in the project lives here, and only here.

Why: in the review they will "change one constraint" (slower interceptor,
more radar noise, longer launch delay, ...). If every constant is in this
file, that change is a one-line edit and we can re-run everything live.

Each value is tagged:
  [PDF]        given by the assignment
  [ASSUMPTION] our choice, because the PDF leaves it open — listed in README
  [TUNING]     a knob of our own algorithm, chosen by experiment
"""

# ---------------------------------------------------------------------------
# Site
# ---------------------------------------------------------------------------
PROTECTED_RADIUS_M = 500.0          # [PDF] must intercept A before it is this close

# ---------------------------------------------------------------------------
# Radar
# ---------------------------------------------------------------------------
RADAR_RATE_HZ = 10.0                # [PDF] reports per second per object
RADAR_DT_S = 1.0 / RADAR_RATE_HZ    # time between reports (0.1 s)
RADAR_SIGMA_M = 15.0                # [PDF] position noise, 1 sigma, per axis [ASSUMPTION: per axis, independent x/y/z]
RADAR_DROP_PROB = 0.10              # [PDF] ~1 in 10 reports never arrives [ASSUMPTION: independent random drops]

# ---------------------------------------------------------------------------
# Interceptor
# ---------------------------------------------------------------------------
INTERCEPTOR_DELAY_S = 3.0           # [PDF] time from launch order to leaving the container
INTERCEPTOR_SPEED_MPS = 60.0        # [PDF] straight line, constant speed
KILL_RADIUS_M = 15.0                # [ASSUMPTION] interceptor "hits" if it passes within this distance of the target.
                                    #   The PDF says "straight line" = no terminal seeker, so our aim must be good.
INTERCEPTORS_IN_CONTAINER = 4       # [ASSUMPTION] how many interceptors the container holds
INTERCEPTOR_REARM_S = 15.0          # [ASSUMPTION] one interceptor is ready at t = 0. After each launch the next one
                                    #   is ready this many seconds later (Part 2 Q3: "one interceptor is ready").

# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------
SIM_DURATION_S = 130.0              # [ASSUMPTION] A (3000 m at 25 m/s) reaches the site at t=120 s; run a bit longer
N_SEEDS = 50                        # [PDF] Monte Carlo runs
HELD_OUT_FIRST_SEED = 1000          # [ASSUMPTION] Part 1.5 also runs seeds 1000..1049. No tuning step ever looked at
                                    #   them (tracker tuning used 0-19, decision checks 0-49), so they test the knobs fairly.

# ---------------------------------------------------------------------------
# Object A — the threat
# ---------------------------------------------------------------------------
A_START_RANGE_M = 3000.0            # [PDF]
A_SPEED_MPS = 25.0                  # [PDF] flies straight at the site
A_ALTITUDE_M = 100.0                # [ASSUMPTION] starts at this altitude, 3 km out horizontally, at a random
                                    #   bearing, and flies a straight 3D line to the site at (0,0,0)
                                    #   (i.e. a shallow dive). Distances to the site are 3D everywhere.

# ---------------------------------------------------------------------------
# Object B — the passer
# ---------------------------------------------------------------------------
B_SPEED_MPS = 30.0                  # [PDF]
B_MIN_MISS_M = 700.0                # [PDF] closest approach is never below this
B_MAX_MISS_M = 900.0                # [ASSUMPTION] closest approach drawn uniformly in [700, 900] m per seed
B_ALTITUDE_M = 120.0                # [ASSUMPTION]
B_T_CLOSEST_S = (40.0, 90.0)        # [ASSUMPTION] B reaches its closest point somewhere in this time window,
                                    #   so it overlaps in time with A's approach (the confusing case)

# ---------------------------------------------------------------------------
# Object C — the bird
# ---------------------------------------------------------------------------
C_SPEED_MPS = 12.0                  # [PDF] "about 12 m/s"
C_CENTER_RANGE_M = 900.0            # [PDF] wanders around 900 m out
C_ALTITUDE_M = 60.0                 # [ASSUMPTION]
C_TURN_RATE_SIGMA = 0.3             # [ASSUMPTION] random heading changes (rad/s, 1 sigma) — the "wander"
C_DASH_PROB_PER_S = 0.05            # [ASSUMPTION] chance per second of starting a dash toward the site
C_DASH_DURATION_S = (3.0, 6.0)      # [ASSUMPTION] a dash lasts "a few seconds"
C_LEASH_M = 150.0                   # [ASSUMPTION] bird turns back if it drifts this far from 900 m ring
C_LEASH_GAIN = 1.0                  # [ASSUMPTION] how hard it turns back (rad/s per rad of heading error)

# ---------------------------------------------------------------------------
# Tracker (filled in when we build tracker.py)
# ---------------------------------------------------------------------------
TRACKER_PROCESS_NOISE = 0.01        # [TUNING] "q", in m^2/s^3. How much the filter expects a target's velocity
                                    #   to change on its own. Over T seconds it allows a velocity drift of about
                                    #   sqrt(q*T) m/s. Low q = long memory (smooth, accurate on straight flyers,
                                    #   slow to notice turns). High q = short memory (fast, noisy).
                                    #   Chosen with part1_2_tracker/src/tune.py (output/tuning.txt):
                                    #   0.01 aims a 15 s prediction at A to ~8 m RMS (vs ~14 m at 0.1),
                                    #   inside the 15 m kill radius. Cost: it is overconfident on the
                                    #   bird -> we add the fit score below to catch that.
TRACKER_FIT_WINDOW_S = 5.0          # [TUNING] fit score = average NIS over this many seconds of reports.
                                    #   ~3 = flies like a straight line. Measured over 20 seeds at q=0.01:
                                    #   A/B median 3.0, max 4.5; bird median 9, often >20.
TRACKER_INIT_VEL_SIGMA_MPS = 50.0   # [ASSUMPTION] velocity uncertainty of a brand new track: "anything up to
                                    #   ~50 m/s in any direction". Faster than any object we expect.
TRACK_DROP_AFTER_S = 5.0            # [ASSUMPTION] stop tracking an object after this long with no reports.
                                    #   Longer than the 3 s radar outage in Part 2 Q2, so we coast through it.

# ---------------------------------------------------------------------------
# Decision (part1_3_decision/src/decision.py)
# ---------------------------------------------------------------------------
MIN_TRACK_AGE_S = 5.0               # [TUNING] don't judge a track younger than this: velocity is still settling
                                    #   and the fit score needs ~2.5 s of reports before it exists at all.
THREAT_CONFIDENCE_SIGMA = 2.0       # [TUNING] "will come inside 500 m" must hold even if the predicted closest
                                    #   approach is this many sigma larger than estimated. Higher = more
                                    #   certain before we call something a threat, but later.
DRONE_MIN_SPEED_MPS = 18.0          # [TUNING] slower than this does not look like a drone (bird ~12 m/s,
                                    #   A 25, B 30). Halfway between bird and threat.
MAX_FIT_NIS = 6.0                   # [TUNING] fit score above this = not flying a straight line. A and B
                                    #   never exceeded 4.5 over 20 seeds; the bird's median is ~9.
THREAT_PERSIST_S = 3.0              # [TUNING] the threat test must hold this long without a break before
                                    #   we may launch. Rides out a single noisy fit-score blip.
INTERCEPT_MARGIN_M = 100.0          # [TUNING] plan the intercept at least this far outside the 500 m line.
                                    #   100 m is ~1.2 s of closing time for A vs the interceptor (85 m/s).
LAUNCH_LEAD_S = 5.0                 # [TUNING] launch when the latest safe launch moment is this close, not
                                    #   earlier. Waiting shortens the flight (aim error = velocity error x
                                    #   flight time) and gives the target less time to change its mind.

# More than one threat (decision.py, Decider._assign) -------------------------
SHARED_SHOT_MARGIN_M = 9.0          # [TUNING] two threats share ONE interceptor, aimed at their midpoint, only if
                                    #   at the meeting each is at least this far inside the kill radius:
                                    #   separation / 2 <= KILL_RADIUS_M - 9 m, i.e. at most 12 m apart.
                                    #   9 m = the 95th-percentile true miss over 100 runs (Part 1.5), so both
                                    #   are likely inside the reach even with a typical aim error.
MAKE_TIME_FOR_NEXT = True           # [TUNING] with several threats queued, launch the most urgent one early
                                    #   enough that the next interceptor is ready in time for the next threat.
                                    #   With one threat this changes nothing.
