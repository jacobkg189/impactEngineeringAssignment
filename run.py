"""
run.py — the one command. Runs every part in PDF order.

    .venv/bin/python run.py            # seed 0
    .venv/bin/python run.py --seed 7

Each part can also run on its own, e.g.  python -m part1_1_generator.run
"""

import argparse

from part1_1_generator.run import run as run_generator
from part1_2_tracker.run import run as run_tracker
from part1_3_decision.run import run as run_decision
from part1_4_show_it.run import run as run_show_it
from part1_5_checks.run import run as run_checks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=0)
    seed = parser.parse_args().seed

    run_generator(seed)
    run_tracker(seed)
    run_decision(seed)
    run_show_it(seed)
    run_checks()          # 1.5 runs its own 2 x 50 seeds, independent of --seed


if __name__ == "__main__":
    main()
