"""
files.py — the ONE place where the data formats are defined.

We pass data around as numpy "structured arrays": a table where every row is
one record and columns are accessed by name, e.g. reports["x_m"] gives the
whole x column. It behaves like a tiny spreadsheet without needing pandas.

The tables, in the order the data flows:

  TRUTH      (world side only)  track_id, time_s, x_m, y_m, z_m, vx_mps, vy_mps, vz_mps
  REPORTS    (what radar sends) track_id, time_s, x_m, y_m, z_m
  ESTIMATES  (tracker output)   REPORTS + velocity + how unsure + fit score
  DECISIONS  (decision output)  one row per object per tick: status and the numbers behind it
  LAUNCHES   (decision output)  one row per launch order: when, aim point, expected intercept, WHY

On disk they are plain CSV files, readable in Excel or any text editor.
"""

import csv
import numpy as np

REPORT_DTYPE = np.dtype([
    ("track_id", "U8"),   # "A", "B", "C" — short text label
    ("time_s", "f8"),     # f8 = 64-bit float
    ("x_m", "f8"),
    ("y_m", "f8"),
    ("z_m", "f8"),
])

TRUTH_DTYPE = np.dtype(REPORT_DTYPE.descr + [
    ("vx_mps", "f8"),
    ("vy_mps", "f8"),
    ("vz_mps", "f8"),
])

# What the tracker outputs: one row per object per 0.1 s tick.
ESTIMATE_DTYPE = np.dtype(TRUTH_DTYPE.descr + [
    ("pos_err_m", "f8"),            # how far off the filter THINKS its position is (1 sigma, 3D)
    ("vel_err_mps", "f8"),          # same for velocity
    ("n_reports", "i8"),            # how many reports this track has absorbed so far
    ("time_since_report_s", "f8"),  # 0 if a report arrived this tick; grows while coasting
    ("fit_nis", "f8"),              # average NIS over the last few seconds: ~3 = straight flyer,
                                    #   well above 3 = turning / wandering. NaN until enough reports.
])

# What the decision step records every tick for every object: its current verdict
# and every number that verdict was based on (so Part 1.4 can show "why").
DECISION_DTYPE = np.dtype([
    ("track_id", "U8"),
    ("time_s", "f8"),
    ("status", "U12"),              # young / clear / slow / erratic / threat / confirmed / queued / launch / launched / too_late
                                    #   (queued = due for launch but no interceptor is ready yet)
    ("age_s", "f8"),                # how long we have been tracking this object
    ("speed_mps", "f8"),            # estimated speed
    ("closest_approach_m", "f8"),   # if it flies on straight, how close to the site it will get
    ("closest_sigma_m", "f8"),      # 1-sigma uncertainty of that number
    ("fit_nis", "f8"),              # copied from the tracker
    ("intercept_range_m", "f8"),    # if we ordered a launch now, how far out would we meet it (NaN = cannot catch)
    ("intercept_time_s", "f8"),     # ...and at what time
    ("aim_x_m", "f8"), ("aim_y_m", "f8"), ("aim_z_m", "f8"),
    ("deadline_in_s", "f8"),        # seconds until an intercept would fall inside the margin (0 = past, inf = never)
    ("threat_held_s", "f8"),        # how long the threat test has held without a break
])

# One row per threat a launch order is aimed at. Usually one interceptor = one row. A shared shot
# (one interceptor aimed between two threats flying close together) gives two rows with the same
# interceptor number, each naming the other in shared_with.
LAUNCH_DTYPE = np.dtype([
    ("track_id", "U8"),
    ("interceptor", "i8"),          # 1, 2, ... in launch order
    ("shared_with", "U8"),          # the other threat this interceptor is aimed at, "" if none
    ("time_s", "f8"),               # when the order was given
    ("leave_time_s", "f8"),         # order + 3 s
    ("intercept_time_s", "f8"),     # when we expect to meet the target
    ("aim_x_m", "f8"), ("aim_y_m", "f8"), ("aim_z_m", "f8"),   # the intercept point we aim for
    ("intercept_range_m", "f8"),    # distance of that point from the site
    ("flight_s", "f8"),             # interceptor time in the air
    ("aim_sigma_m", "f8"),          # how far off we expect the target to be from the aim point (1 sigma)
    # WHY — the numbers that triggered it
    ("closest_approach_m", "f8"),
    ("closest_sigma_m", "f8"),
    ("speed_mps", "f8"),
    ("fit_nis", "f8"),
    ("threat_held_s", "f8"),
    ("deadline_in_s", "f8"),
    ("n_reports", "i8"),
    ("time_since_report_s", "f8"),
])


# Part 1.5: one row per simulated run, scored against the truth. "A" is the threat, B and C
# must never be launched at. Margins say how close each guard came to failing.
RUN_RESULT_DTYPE = np.dtype([
    ("seed", "i8"),
    ("n_launches", "i8"),
    ("wrong_launches", "i8"),            # launches at anything but A (B or C) — each one is a failure
    ("a_launches", "i8"),
    ("a_contact", "i8"),                 # 1 = the interceptor really came within the kill radius of A
    ("a_outside_500", "i8"),             # 1 = contact AND it happened outside 500 m: the PDF's success
    ("a_order_time_s", "f8"),
    ("a_range_at_order_m", "f8"),        # where A really was when we ordered the launch
    ("a_planned_range_m", "f8"),         # where the decision step expected to meet it
    ("a_intercept_range_m", "f8"),       # where they really met (distance from the site)
    ("a_pass_m", "f8"),                  # true closest pass, interceptor to A
    ("a_aim_error_m", "f8"),             # aim point vs where A really was at the planned time
    ("a_aim_sigma_m", "f8"),             # the aim error the system CLAIMED (1 sigma)
    ("a_spare_s", "f8"),                 # how long before A would have crossed 500 m did we meet it
    ("a_min_speed_mps", "f8"),           # A's slowest estimated speed while heading in (vs the drone-speed test)
    ("b_min_band_edge_m", "f8"),         # B's tightest "closest approach + 2 sigma" (heading in if < 500 m)
    ("b_max_threat_held_s", "f8"),
    ("c_heading_in_s", "f8"),            # how long the bird's track passed the heading-in test
    ("c_top_speed_heading_in_mps", "f8"),  # the bird's fastest estimated speed while heading in (vs the drone-speed test)
    ("c_max_threat_held_s", "f8"),
])


def positions(table):
    """Return the x, y, z columns as an (N, 3) array — handy for math."""
    return np.column_stack([table["x_m"], table["y_m"], table["z_m"]])


def rows_for(table, track_id):
    """All rows belonging to one object, e.g. rows_for(truth, "A")."""
    return table[table["track_id"] == track_id]


def write_table(table, path):
    """Write a structured array to CSV with a header line."""
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(table.dtype.names)
        for row in table:
            writer.writerow(_format_row(row, table.dtype.names))


def read_table(path, dtype):
    """Read a CSV written by write_table back into a structured array."""
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        rows = [tuple(_parse(r[name], dtype[name]) for name in dtype.names) for r in reader]
    return np.array(rows, dtype=dtype)


def read_reports(path):
    return read_table(path, REPORT_DTYPE)


def read_truth(path):
    return read_table(path, TRUTH_DTYPE)


def read_estimates(path):
    return read_table(path, ESTIMATE_DTYPE)


def read_decisions(path):
    return read_table(path, DECISION_DTYPE)


def read_launches(path):
    return read_table(path, LAUNCH_DTYPE)


def read_run_results(path):
    return read_table(path, RUN_RESULT_DTYPE)


def _format_row(row, names):
    out = []
    for name in names:
        value = row[name]
        if row.dtype[name].kind in ("U", "i"):   # text and integer columns as they are
            out.append(str(value))
        elif name == "time_s":
            out.append(f"{value:.1f}")   # radar ticks are every 0.1 s
        else:
            out.append(f"{value:.3f}")   # millimetre precision is plenty
    return out


def _parse(text, field_dtype):
    if field_dtype.kind == "U":
        return text
    if field_dtype.kind == "i":
        return int(text)
    return float(text)
