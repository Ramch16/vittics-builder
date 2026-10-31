"""Run benchmark slots under the two conditions and write schema-v2 run records.

    python -m benchmark.harness --schedule benchmark/schedule-20261031.json --out <folder> [--slots 1-4]

Conditions (decisions D8, D11), identical inputs: the frozen task spec as docs/PRD.md, the starter tree, the
public tests, the same builder role and model, the same attempt limit (1 + max_rework).
- multi_agent: the Vittics task loop (`Pipeline._run_task`): builder, independent code review and QA, rework.
- single_agent: one persistent builder with the same tools; after each attempt the public tests run and their
  output is its feedback, up to the same attempt limit. No reviewers, no delegation.
Every final tree is evaluated by `benchmark.oracle` in a separate temporary folder (hidden tests).

Only the offline MockProvider is allowed (records are data_kind "synthetic-mock"). Real-provider runs need an
approved freeze manifest and spending authorization (protocol P07/P10), which this harness does not have.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from vittics_builder.benchmarks import SCHEMA_PATH, check_semantics, summarize_records, validate_record

from . import oracle

ROOT = Path(__file__).resolve().parent.parent
BUILDER_ROLE = "backend_engineer"


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def harness_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True,
                              check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "0" * 40


def prompt_for(spec: str) -> str:
    return ("Implement the specification in docs/PRD.md inside app/. Public tests are in tests/; run them with "
            "`python -m pytest -q tests`. Do not edit tests/.")


def seed_workspace(ws, task_dir: Path) -> None:
    for item in (task_dir / "starter").iterdir():
        dest = ws.root / item.name
        shutil.copytree(item, dest, dirs_exist_ok=True) if item.is_dir() else shutil.copy2(item, dest)
    (ws.root / "docs").mkdir(exist_ok=True)
    (ws.root / "docs" / "PRD.md").write_text((task_dir / "spec.md").read_text(encoding="utf-8"), encoding="utf-8")
    (ws.root / "docs" / "ARCHITECTURE.md").write_text(
        "# Architecture\n\nOne Python package, `app/`, as named in docs/PRD.md. Tests use pytest.\n", encoding="utf-8")
    ws.commit("Benchmark starter")


def public_tests(ws) -> tuple[bool, str]:
    out = ws.run_command(f"{sys.executable} -m pytest -q -p no:cacheprovider tests", max_seconds=300)
    return out.splitlines()[0] == "exit code 0", out


def run_slot(slot: dict, out_dir: Path, provider_factory) -> dict:
    from vittics_builder.company import Company
    from vittics_builder.pipeline import PipelineError
    task_dir = oracle.task_dir(slot["task_id"])
    spec = (task_dir / "spec.md").read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix=f"bench-{slot['run_id']}-") as tmp:
        co = Company(Path(tmp), provider=provider_factory(), create=True)
        p = co.pipeline.create_project(task_dir.name, spec.splitlines()[0].lstrip("# "))
        ws = co.pipeline.workspace(co.pipeline.project(p["id"]))
        seed_workspace(ws, task_dir)
        attempts_allowed = 1 + co.pipeline.max_rework(p["id"])
        started, t0 = stamp(), time.monotonic()
        blocker, release, rework = None, "not_reached", 0
        status = "incomplete"
        try:
            if slot["condition"] == "multi_agent":
                now = stamp()
                tid = co.db.run("INSERT INTO tasks (project_id, key, title, description, role, status, created_at, "
                                "updated_at) VALUES (?,?,?,?,?,?,?,?)", p["id"], slot["task_id"].lower(),
                                f"Implement {task_dir.name}", spec + "\n\n" + prompt_for(spec), BUILDER_ROLE, "todo",
                                now, now)
                done = co.pipeline._run_task(co.pipeline.project(p["id"]), {"id": tid}, ws)
                row = co.db.one("SELECT status, attempts FROM tasks WHERE id=?", tid)
                rework = row["attempts"]
                release = "released" if row["status"] == "done" else "release_blocked"
                status = "completed" if done else "failed"
            else:
                agent = co.org.pick(role=BUILDER_ROLE, project_id=p["id"])
                feedback = ""
                for attempt in range(attempts_allowed):
                    ask = spec + "\n\n" + prompt_for(spec) + (f"\n\nPublic tests failed:\n{feedback}" if feedback else "")
                    res = co.runtime.run(agent, ask, ws, project_id=p["id"], meta={"purpose": "benchmark"})
                    ws.commit(f"single-agent attempt {attempt + 1}")
                    passed, feedback = public_tests(ws)
                    if passed and res.completed:
                        release = "released"
                        break
                    rework = attempt + 1 if attempt + 1 < attempts_allowed else attempt
                else:
                    release = "release_blocked"
                status = "completed"
        except PipelineError as exc:
            blocker, status, release = str(exc)[:500], "blocked", "release_blocked"
        wall = round(time.monotonic() - t0, 3)
        ended = stamp()
        result = oracle.evaluate(slot["task_id"], ws.root)
        log = out_dir / "oracle" / f"{slot['run_id']}.json"
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(json.dumps(result, indent=2), encoding="utf-8")
        usage = co.db.one("SELECT COALESCE(SUM(input_tokens),0) AS i, COALESCE(SUM(output_tokens),0) AS o, "
                          "COALESCE(SUM(cost),0) AS c, COALESCE(MIN(priced),1) AS priced, COUNT(*) AS n FROM usage "
                          "WHERE project_id=?", p["id"])
        reviews = co.db.one("SELECT COUNT(*) AS n FROM reviews WHERE project_id=?", p["id"])["n"] \
            if co.db.one("SELECT 1 FROM sqlite_master WHERE name='reviews'") else 0
    hashes = oracle.package_hashes(slot["task_id"])
    accepted = result["all_passed"] is True
    terminal = ("blocked" if status == "blocked" else "accepted" if accepted else
                "rejected" if status == "completed" else "failed")
    record = {
        "schema_version": 2, "data_kind": "synthetic-mock", "experiment_id": "mock-pilot-20261031",
        "run_id": slot["run_id"], "task_id": slot["task_id"], "condition": slot["condition"], "repeat": slot["repeat"],
        "source": {"harness_commit": harness_commit(), "starter_tree_sha256": hashes["starter"]},
        "hashes": {"task": hashes["task"], "prompt": sha(prompt_for(spec)), "oracle": hashes["oracle"],
                   "config": sha(json.dumps({"builder_role": BUILDER_ROLE, "attempts": attempts_allowed}))},
        "engine": {"provider": "mock", "model": "mock", "model_version": None, "engine": "mock", "engine_version": None},
        "environment_ref": f"python-{sys.version.split()[0]}-{sys.platform}",
        "started_at": started, "ended_at": ended, "terminal_status": terminal, "blocker": blocker,
        "acceptance": {"checks": [{"id": c["id"], "passed": c["passed"]} for c in result["checks"]],
                       "all_passed": result["all_passed"], "release_outcome": release,
                       "oracle": {"kind": "independent_hidden", "evaluated_tree": result["evaluated_tree_sha256"][:40],
                                  "run_ref": f"oracle/{slot['run_id']}.json"}},
        "caps": {"max_total_tokens": None, "max_wall_seconds": None, "max_cost": None},
        "retries": {"builder_rework": rework, "reviewer_retry": 0, "infrastructure_retry": 0},
        "human_interventions": [],
        "usage": {"input_tokens": usage["i"], "output_tokens": usage["o"], "cache_read_tokens": None,
                  "cache_write_tokens": None},
        "cost": {"amount": 0.0, "currency": "USD", "basis": "billed", "price_source": "mock provider (no charge)",
                 "price_source_date": ended[:10]},
        "timing": {"wall_seconds": wall, "active_union_seconds": None, "summed_agent_seconds": None,
                   "waits": {"human": 0, "provider_unavailable": 0, "infrastructure": 0, "unclassified": None}},
        "artifacts": [{"path": f"oracle/{slot['run_id']}.json", "sha256": hashlib.sha256(log.read_bytes()).hexdigest()}],
        "ai_assistance": "Agents were the offline MockProvider (scripted, no model).",
        "limitations": ["MockProvider agents are scripted and do not attempt the task; this record tests the "
                        "harness, not either condition.", f"independent reviews recorded: {reviews}"],
    }
    return record


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--schedule", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--slots", help="e.g. 1-4 (default: all)")
    ap.add_argument("--provider", default="mock", choices=["mock"])
    args = ap.parse_args(argv)
    from vittics_builder.llm import MockProvider
    schedule = json.loads(Path(args.schedule).read_text(encoding="utf-8"))
    slots = schedule["slots"]
    if args.slots:
        lo, _, hi = args.slots.partition("-")
        slots = [s for s in slots if int(lo) <= s["slot"] <= int(hi or lo)]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    schema = json.loads((ROOT / SCHEMA_PATH).read_text(encoding="utf-8"))
    records = []
    for slot in slots:
        records.append(run_slot(slot, out, MockProvider))
        print(f"slot {slot['slot']:>2} {slot['run_id']:<26} {records[-1]['terminal_status']}", flush=True)
    errors = {r["run_id"]: validate_record(r, schema) for r in records}
    semantics = check_semantics(records)
    (out / "records.jsonl").write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in records), encoding="utf-8")
    (out / "validation.json").write_text(json.dumps({"schema": errors, "semantics": semantics}, indent=2), encoding="utf-8")
    (out / "summary.json").write_text(json.dumps(summarize_records(records), indent=2, sort_keys=True), encoding="utf-8")
    return 0 if not any(errors.values()) and not semantics else 1


if __name__ == "__main__":
    raise SystemExit(main())
