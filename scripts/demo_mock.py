"""Offline demonstration (Week 13): a brief goes through the whole Vittics pipeline with scripted mock agents,
the demo approving each gate as the CEO or CTO; then one benchmark slot per condition runs and is judged by the
independent oracle. No model, no API key, no network, no cost.

    python scripts/demo_mock.py [--out demo-output]

Everything printed comes from the run. Mock agents are scripted, so the product they "build" is a placeholder
and the benchmark runs are rejected by the oracle; the demo shows the workflow, gates, reviews and evidence,
not agent quality.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchmark.harness import run_slot                     # noqa: E402
from vittics_builder.company import Company                # noqa: E402
from vittics_builder.llm import MockProvider               # noqa: E402


def pipeline_demo(root: Path) -> list[str]:
    co = Company(root, provider=MockProvider(), create=True)
    p = co.pipeline.create_project("Greeter", "A tiny Python library that greets people by name, with tests.")
    log = [f"project created: {p['name']} (stage {co.pipeline.project(p['id'])['stage']})"]
    state = co.pipeline.advance(p["id"])
    for _ in range(12):
        log.append(f"stage: {state['stage']}")
        pending = [(role, a) for role in ("ceo", "cto") for a in co.pipeline.inbox(role)
                   if a["project_id"] == p["id"] and a["kind"] not in ("hr", "hire")]
        if not pending:
            break
        role, a = pending[0]
        log.append(f"  gate: {a['title']} -> approved by {role.upper()} (demo)")
        co.pipeline.decide(a["id"], role, "approved", "Approved in the offline demo.")
        state = co.pipeline.advance(p["id"])
    tasks = co.db.all("SELECT key, status FROM tasks WHERE project_id=? AND key NOT LIKE 'stage-%'", p["id"])
    reviews = co.db.one("SELECT COUNT(*) AS n FROM reviews WHERE project_id=?", p["id"])["n"]
    log.append(f"final stage: {co.pipeline.project(p['id'])['stage']}; tickets: "
               + ", ".join(f"{t['key']}={t['status']}" for t in tasks) + f"; independent reviews: {reviews}")
    return log


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", default="demo-output")
    args = ap.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        lines = ["# Part 1: brief to release (mock agents)"] + pipeline_demo(Path(tmp))
    lines.append("# Part 2: one benchmark slot per condition, judged by the hidden-test oracle")
    for condition in ("multi_agent", "single_agent"):
        r = run_slot({"slot": 0, "task_id": "T07", "repeat": 1, "condition": condition,
                      "run_id": f"demo-T07-{condition}"}, out, MockProvider)
        passed = sum(c["passed"] is True for c in r["acceptance"]["checks"])
        lines.append(f"{condition}: {r['terminal_status']}, release {r['acceptance']['release_outcome']}, "
                     f"oracle {passed}/{len(r['acceptance']['checks'])} checks, rework {r['retries']['builder_rework']}")
        (out / f"demo-T07-{condition}.json").write_text(json.dumps(r, indent=2), encoding="utf-8")
    (out / "demo.log").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
