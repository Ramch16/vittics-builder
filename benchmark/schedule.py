"""Frozen, counterbalanced run schedule (decision D10: 3 repeats per task per condition, seed 20261031).

    python -m benchmark.schedule --seed 20261031 > benchmark/schedule-20261031.json

For every task and repeat, both conditions run back to back in a random order; across a task's three
repeats each condition goes first at least once. The order of (task, repeat) blocks is then shuffled.
Python's `random.Random(seed)` makes the schedule reproducible from the seed alone.
"""
from __future__ import annotations

import argparse
import json
import random

from .oracle import TASKS

CONDITIONS = ("multi_agent", "single_agent")


def build(seed: int, repeats: int = 3) -> dict:
    rng = random.Random(seed)
    tasks = sorted(p.name.split("-", 1)[0] for p in TASKS.iterdir() if p.is_dir())
    blocks = []
    for task in tasks:
        firsts = [CONDITIONS[i % 2] for i in range(repeats)]
        rng.shuffle(firsts)
        for repeat, first in enumerate(firsts, start=1):
            second = CONDITIONS[1] if first == CONDITIONS[0] else CONDITIONS[0]
            blocks.append([(task, repeat, first), (task, repeat, second)])
    rng.shuffle(blocks)
    slots = [{"slot": i + 1, "task_id": t, "repeat": r, "condition": c,
              "run_id": f"{t}-{c}-r{r}"} for i, (t, r, c) in enumerate(run for block in blocks for run in block)]
    return {"seed": seed, "repeats": repeats, "conditions": list(CONDITIONS), "tasks": tasks,
            "algorithm": "python random.Random(seed); per-task shuffled first-condition list; shuffled blocks",
            "slots": slots}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=20261031)
    ap.add_argument("--repeats", type=int, default=3)
    args = ap.parse_args(argv)
    print(json.dumps(build(args.seed, args.repeats), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
