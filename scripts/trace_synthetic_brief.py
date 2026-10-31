"""Trace one synthetic brief from requirements to export on the offline mock provider, and save what happened.

    python scripts/trace_synthetic_brief.py --out evidence/week1/<capture-id>/synthetic-trace.json

Every agent is the scripted MockProvider, so this exercises orchestration, gates and the evidence ledger only;
it says nothing about AI coding quality. Each human gate is approved here by the script, standing in for the
CEO and CTO; the trace records that as `decided_by_script`, not as a human decision.
The output is labelled data_kind "synthetic-mock". Timestamps and commit SHAs differ on every run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path

os.environ["VITTICS_PROVIDER"] = "mock"
for name in [n for n in os.environ if "KEY" in n.upper() or "TOKEN" in n.upper() or n.startswith("GIT_CONFIG_")]:
    os.environ.pop(name)       # nothing here may reach a paid provider; git config variables go as a set

from vittics_builder.company import Company           # noqa: E402
from vittics_builder.delivery import export_product   # noqa: E402
from vittics_builder.llm import MockProvider          # noqa: E402

BRIEF = "A small Python library with a core module and a supporting module, each with unit tests."


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    with tempfile.TemporaryDirectory(prefix="vb-trace-") as tmp:
        co = Company(Path(tmp) / "company", provider=MockProvider(), create=True)
        p = co.pipeline.create_project("Synthetic Library", BRIEF, by="ceo")
        pid, steps = p["id"], []
        state = co.pipeline.advance(pid)
        for _ in range(40):
            pending = [a for a in co.pipeline.inbox() if a["project_id"] == pid and a["kind"] not in ("hr", "hire")]
            if not pending:
                break
            a = pending[0]
            before = co.pipeline.project(pid)["stage"]
            co.pipeline.decide(a["id"], a["required_role"], "approved", "Approved by the synthetic trace script.")
            state = co.pipeline.advance(pid)
            steps.append({"approval_id": a["id"], "kind": a["kind"], "required_role": a["required_role"],
                          "stage_before": before, "stage_after": state["stage"], "decided_by_script": True})
        ledger = []
        for row in co.db.all("SELECT * FROM verification_runs WHERE project_id=? ORDER BY id", pid):
            r = json.loads(row["report"])
            ledger.append({"ledger_id": row["id"], "source_commit": row["source_commit"], "passed": r.get("passed"),
                           "release_eligible": r.get("release_eligible"), "coverage": r.get("coverage"),
                           "requirements": [{k: q.get(k) for k in ("id", "status", "release_eligible")}
                                            for q in r.get("requirements", [])],
                           "checks": [{"id": c["id"], "passed": c["passed"]} for c in r.get("checks", [])],
                           "errors": r.get("errors"), "contract_sha256": r.get("contract_sha256"),
                           "source_sha256": r.get("source_sha256"),
                           "verifier_sha256": (r.get("verifier") or {}).get("sha256")})
        release = next((s for s in reversed(steps) if s["kind"] == "release"), None)
        approvals = co.db.all("SELECT id, kind, required_role, status, decided_by, payload FROM approvals "
                              "WHERE project_id=? ORDER BY id", pid)
        release_payload = next((json.loads(a["payload"]) for a in reversed(approvals) if a["kind"] == "release"), {})
        exported = None
        if co.pipeline.project(pid)["stage"] in ("done", "live"):
            zipped = export_product(co.pipeline, pid, Path(tmp) / "export" / "release.zip")
            with zipfile.ZipFile(zipped) as z:
                names = sorted(z.namelist())
            exported = {"sha256": hashlib.sha256(zipped.read_bytes()).hexdigest(), "files": names,
                        "contains_verification_report": "docs/VERIFICATION.json" in names}
        ws = co.pipeline.workspace(co.pipeline.project(pid))
        trace = {"schema_version": 1, "data_kind": "synthetic-mock", "brief": BRIEF,
                 "python": sys.version.split()[0], "final_stage": co.pipeline.project(pid)["stage"],
                 "gates": steps,
                 "approvals": [{k: a[k] for k in ("id", "kind", "required_role", "status", "decided_by")} for a in approvals],
                 "release_approval_payload": {k: release_payload.get(k) for k in ("verified_head", "ledger_id", "inconclusive")},
                 "verification_ledger": ledger, "release_tag": ws.git("rev-parse", "release") if exported else None,
                 "release_tree_matches_verified_tree": (ws.git("rev-parse", "release^{tree}") ==
                                                        ws.git("rev-parse", f"{release_payload['verified_head']}^{{tree}}"))
                 if exported and release_payload.get("verified_head") else None,
                 "export": exported, "release_gate_seen": bool(release),
                 "limitations": ["MockProvider scripts every agent; no AI coding quality is exercised.",
                                 "Gates were approved by this script standing in for the CEO and CTO.",
                                 "Timestamps and commit SHAs differ on every run."]}
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(trace, indent=2) + "\n", encoding="utf-8")
    print(out)
    return 0 if trace["final_stage"] == "done" and exported else 1


if __name__ == "__main__":
    raise SystemExit(main())
