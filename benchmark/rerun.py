"""Rerun one scheduled slot without losing the original (Week 19).

    python -m benchmark.rerun --schedule benchmark/schedule-20261031.json --out <folder> --slot 7 \
        --reason "infrastructure: runner lost network" [--category infrastructure]

The original record stays in records.jsonl. The rerun is appended as `<run_id>-rerun<n>` and a deviation
entry (slot, reason, category, the original's status, the time) is appended to deviations.jsonl. Only
infrastructure reruns are allowed by default; a rerun because a result was disliked is the optional stopping
the protocol forbids, so `--category outcome` is refused.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .harness import run_slot

ALLOWED = {"infrastructure", "provider_unavailable", "harness_bug"}


def rerun(schedule: dict, out: Path, slot_no: int, reason: str, category: str, provider_factory, caps=None) -> dict:
    if category not in ALLOWED:
        raise SystemExit(f"Rerun category '{category}' is not allowed (allowed: {', '.join(sorted(ALLOWED))}).")
    if not reason.strip():
        raise SystemExit("A rerun needs a reason.")
    [slot] = [s for s in schedule["slots"] if s["slot"] == slot_no]
    records_path = out / "records.jsonl"
    records = [json.loads(l) for l in records_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    originals = [r for r in records if r["run_id"] == slot["run_id"]]
    if not originals:
        raise SystemExit(f"No original record for {slot['run_id']}; run the slot first.")
    n = 1 + sum(r["run_id"].startswith(slot["run_id"] + "-rerun") for r in records)
    again = {**slot, "run_id": f"{slot['run_id']}-rerun{n}"}
    record = run_slot(again, out, provider_factory, caps)
    record["limitations"].append(f"Rerun {n} of {slot['run_id']} ({category}): {reason}")
    with records_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")
    entry = {"slot": slot_no, "original_run_id": slot["run_id"], "rerun_id": again["run_id"], "category": category,
             "reason": reason, "original_status": originals[0]["terminal_status"],
             "rerun_status": record["terminal_status"],
             "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    with (out / "deviations.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")
    return entry


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--schedule", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--slot", type=int, required=True)
    ap.add_argument("--reason", required=True)
    ap.add_argument("--category", default="infrastructure")
    args = ap.parse_args(argv)
    from vittics_builder.llm import MockProvider
    schedule = json.loads(Path(args.schedule).read_text(encoding="utf-8"))
    print(json.dumps(rerun(schedule, Path(args.out), args.slot, args.reason, args.category, MockProvider), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
