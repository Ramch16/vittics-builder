"""Results report from run records (Week 11/12): Markdown tables, missingness and sensitivity, no hidden zeros.

    python -m benchmark.report --records <folder>/records.jsonl [--out report.md]

Primary metric (decision D12): hidden-oracle acceptance per started run. Runs whose oracle did not run are
unresolved: the report shows the conservative rate (unresolved = not accepted) and the optimistic bound
(unresolved = accepted), and the count. Repeats are clustered by task, so only task-level summaries are given
(per-task rates, the equal-weight mean, the median and the range of differences); no significance test.
If any record is not `observed` (a real-provider run), the report says these are not results.
"""
from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter
from pathlib import Path

CONDITIONS = ("multi_agent", "single_agent")


def _rate(n: int, d: int) -> str:
    return f"{n}/{d} ({n / d:.0%})" if d else "n/a"


def analyse(records: list[dict]) -> dict:
    out = {"data_kinds": sorted({r["data_kind"] for r in records}), "conditions": {}, "tasks": []}
    for c in CONDITIONS:
        rs = [r for r in records if r["condition"] == c]
        accepted = sum(r["acceptance"]["all_passed"] is True for r in rs)
        unresolved = sum(r["acceptance"]["all_passed"] is None for r in rs)
        released = [r for r in rs if r["acceptance"]["release_outcome"] == "released"]
        costs = [r["cost"]["amount"] for r in rs]
        known = [x for x in costs if x is not None]
        out["conditions"][c] = {
            "runs": len(rs), "accepted": accepted, "unresolved": unresolved,
            "statuses": dict(Counter(r["terminal_status"] for r in rs)),
            "released": len(released),
            "false_releases": sum(r["acceptance"]["all_passed"] is not True for r in released),
            "rework": sum(r["retries"]["builder_rework"] for r in rs),
            "tokens": sum((r["usage"]["input_tokens"] or 0) + (r["usage"]["output_tokens"] or 0) for r in rs)
            if all(r["usage"]["input_tokens"] is not None for r in rs) else None,
            "known_cost_subtotal": round(sum(known), 6), "unknown_cost_runs": len(costs) - len(known),
            "cost_per_accepted": round(sum(known) / accepted, 6) if accepted and len(known) == len(costs) else None,
            "wall_seconds": round(sum(r["timing"]["wall_seconds"] or 0 for r in rs), 3),
        }
    for task in sorted({r["task_id"] for r in records}):
        row = {"task_id": task}
        for c in CONDITIONS:
            rs = [r for r in records if r["task_id"] == task and r["condition"] == c]
            row[c] = (sum(r["acceptance"]["all_passed"] is True for r in rs), len(rs))
        rates = [row[c][0] / row[c][1] if row[c][1] else None for c in CONDITIONS]
        row["difference"] = None if None in rates else rates[0] - rates[1]
        out["tasks"].append(row)
    diffs = [t["difference"] for t in out["tasks"] if t["difference"] is not None]
    out["paired"] = {"tasks": len(diffs), "mean": statistics.fmean(diffs) if diffs else None,
                     "median": statistics.median(diffs) if diffs else None,
                     "min": min(diffs) if diffs else None, "max": max(diffs) if diffs else None}
    return out


def markdown(a: dict) -> str:
    lines = ["# Benchmark report", ""]
    if a["data_kinds"] != ["observed"]:
        lines += [f"> **Not results.** Data kinds: {', '.join(a['data_kinds'])}. These records test the pipeline; "
                  "they say nothing about either condition.", ""]
    lines += ["## Primary metric: hidden-oracle acceptance per started run", "",
              "| Condition | Runs | Accepted (conservative) | Optimistic bound | Unresolved |", "| --- | --- | --- | --- | --- |"]
    for c, v in a["conditions"].items():
        lines.append(f"| {c} | {v['runs']} | {_rate(v['accepted'], v['runs'])} | "
                     f"{_rate(v['accepted'] + v['unresolved'], v['runs'])} | {v['unresolved']} |")
    lines += ["", "## Per task (accepted / runs)", "", "| Task | multi_agent | single_agent | Difference |",
              "| --- | --- | --- | --- |"]
    for t in a["tasks"]:
        d = "n/a" if t["difference"] is None else f"{t['difference']:+.2f}"
        lines.append(f"| {t['task_id']} | {t['multi_agent'][0]}/{t['multi_agent'][1]} | "
                     f"{t['single_agent'][0]}/{t['single_agent'][1]} | {d} |")
    p = a["paired"]
    if p["tasks"]:
        lines += ["", f"Task-paired difference (multi − single) over {p['tasks']} tasks: mean {p['mean']:+.2f}, "
                  f"median {p['median']:+.2f}, range {p['min']:+.2f} to {p['max']:+.2f}. Repeats are clustered by "
                  "task; no significance test is reported."]
    lines += ["", "## Secondary", "", "| Condition | Statuses | Released | False releases | Rework | Tokens | "
              "Known cost | Unknown-cost runs | Cost per accepted | Wall s |", "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for c, v in a["conditions"].items():
        statuses = ", ".join(f"{k} {n}" for k, n in sorted(v["statuses"].items()))
        lines.append(f"| {c} | {statuses} | {v['released']} | {v['false_releases']} | {v['rework']} | "
                     f"{'unknown' if v['tokens'] is None else v['tokens']} | {v['known_cost_subtotal']} | "
                     f"{v['unknown_cost_runs']} | {'undefined' if v['cost_per_accepted'] is None else v['cost_per_accepted']} | "
                     f"{v['wall_seconds']} |")
    lines += ["", "Known cost is a subtotal of runs with a known cost, not a total when any run's cost is unknown. "
              "Cost per accepted run is undefined with no accepted run or with any unknown cost.", ""]
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--records", required=True)
    ap.add_argument("--out")
    args = ap.parse_args(argv)
    records = [json.loads(l) for l in Path(args.records).read_text(encoding="utf-8").splitlines() if l.strip()]
    text = markdown(analyse(records))
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
