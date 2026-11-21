"""
Run Part 1.1 on its own:

    .venv/bin/python -m part1_1_generator.run --seed 0

Writes into part1_1_generator/output/:
    reports_seed0.csv   noisy radar reports with ~10% missing
    truth_seed0.csv     the true paths (kept separate, as the PDF asks)
    world_seed0.png     picture to check the world looks right
"""

import argparse

from common.paths import GENERATOR_OUTPUT
from part1_1_generator.src.generator import generate
from part1_1_generator.src.plot_world import plot_world


def run(seed):
    truth, reports = generate(seed, out_dir=GENERATOR_OUTPUT)
    png = GENERATOR_OUTPUT / f"world_seed{seed}.png"
    plot_world(truth, reports, png, title=f"Generated scenario — seed {seed}")

    print(f"[1.1 generator] seed {seed}: {len(truth)} true rows, {len(reports)} radar reports "
          f"({1 - len(reports) / len(truth):.1%} dropped)")
    for name in (f"reports_seed{seed}.csv", f"truth_seed{seed}.csv", png.name):
        print(f"                wrote part1_1_generator/output/{name}")
    return truth, reports


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=0)
    run(parser.parse_args().seed)
