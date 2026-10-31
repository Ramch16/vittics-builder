"""Paired-input audit (Week 7): did both conditions get the same inputs, and did every scheduled slot run?

    python -m benchmark.audit --schedule benchmark/schedule-20261031.json --records <folder>/records.jsonl

For each task, every record of both conditions must share the task, oracle and config hashes, the starter tree,
the harness commit, the engine (provider, model, version) and the caps. The shared task prompt hash must match
too. The condition-specific wrapper text differs by design: the Vittics task loop adds its ticket instructions,
and the single builder gets public-test output as feedback. That difference is reported, not hidden.
Exit code 0 only if there are no mismatches and no scheduled slot is missing.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

PAIRED = {
    "task hash": lambda r: r["hashes"]["task"],
    "oracle hash": lambda r: r["hashes"]["oracle"],
    "config hash": lambda r: r["hashes"]["config"],
    "shared prompt hash": lambda r: r["hashes"]["prompt"],
    "starter tree": lambda r: r["source"]["starter_tree_sha256"],
    "harness commit": lambda r: r["source"]["harness_commit"],
    "engine": lambda r: json.dumps(r["engine"], sort_keys=True),
    "caps": lambda r: json.dumps(r["caps"], sort_keys=True),
    "data kind": lambda r: r["data_kind"],
}
BY_DESIGN = ["Condition wrappers differ: multi_agent gets the Vittics ticket instructions and reviewer findings; "
             "single_agent gets public-test output as feedback (decision D11)."]


def audit(schedule: dict, records: list[dict]) -> dict:
    by_id = {r["run_id"]: r for r in records}
    missing = [s["run_id"] for s in schedule["slots"] if s["run_id"] not in by_id]
    extra = sorted(set(by_id) - {s["run_id"] for s in schedule["slots"]})
    mismatches = []
    for task in sorted({r["task_id"] for r in records}):
        group = [r for r in records if r["task_id"] == task]
        for name, get in PAIRED.items():
            values = {get(r) for r in group}
            if len(values) > 1:
                mismatches.append({"task_id": task, "field": name,
                                   "values": {r["run_id"]: get(r) for r in group}})
    conditions = {}
    for r in records:
        conditions.setdefault(r["task_id"], {}).setdefault(r["condition"], 0)
        conditions[r["task_id"]][r["condition"]] += 1
    unbalanced = {t: c for t, c in conditions.items() if len(set(c.values())) > 1 or len(c) < 2}
    return {"records": len(records), "scheduled": len(schedule["slots"]), "missing_slots": missing,
            "unscheduled_records": extra, "mismatches": mismatches, "unbalanced_tasks": unbalanced,
            "differences_by_design": BY_DESIGN,
            "passed": not missing and not extra and not mismatches and not unbalanced}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--schedule", required=True)
    ap.add_argument("--records", required=True)
    args = ap.parse_args(argv)
    schedule = json.loads(Path(args.schedule).read_text(encoding="utf-8"))
    records = [json.loads(line) for line in Path(args.records).read_text(encoding="utf-8").splitlines() if line.strip()]
    result = audit(schedule, records)
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
