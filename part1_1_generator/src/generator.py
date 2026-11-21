"""
generator.py — Part 1.1. Glue: seed -> true paths -> radar reports -> two files.

    truth, reports = generate(seed=0, out_dir=GENERATOR_OUTPUT)
    -> part1_1_generator/output/truth_seed0.csv    (answer key; only JUDGE code reads it)
    -> part1_1_generator/output/reports_seed0.csv  (what the SYSTEM side gets)

out_dir=None means "don't write files" (the tests use that).

Seeding: one seed is split into independent random streams, one per object
and one for the radar. So the same seed always gives the same run, and
changing e.g. the radar noise doesn't change the paths the objects fly.
"""

import os
import numpy as np

from .scenario import make_truth
from .radar import observe
from common.files import write_table


def generate(seed, out_dir=None):
    a_seq, b_seq, c_seq, radar_seq = np.random.SeedSequence(seed).spawn(4)
    rngs = {
        "A": np.random.default_rng(a_seq),
        "B": np.random.default_rng(b_seq),
        "C": np.random.default_rng(c_seq),
    }
    truth = make_truth(rngs)
    reports = observe(truth, np.random.default_rng(radar_seq))

    if out_dir is not None:
        os.makedirs(out_dir, exist_ok=True)
        write_table(truth, os.path.join(out_dir, f"truth_seed{seed}.csv"))
        write_table(reports, os.path.join(out_dir, f"reports_seed{seed}.csv"))
    return truth, reports
