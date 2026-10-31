"""Week 1 negative cases (docs/research/week1-audit.md, threat-model.md).

Passing tests pin controls that hold today. Tests marked xfail(strict=True) state what should hold and
does not yet; a fix makes them XPASS, which strict mode reports as a failure until the marker is removed.
Only synthetic projects, fake canary secrets and pytest's temporary folders are used.
"""
import json
import os
import sys

import pytest

from vittics_builder.engines import BUILTIN_ENGINES
from vittics_builder.tools import ToolError, Workspace

PY = sys.executable
CANARY = "canary-FAKE-7f3a91"


def decide_next(co, role):
    [a] = [a for a in co.pipeline.inbox(role) if a["kind"] not in ("hr", "hire")]
    co.pipeline.decide(a["id"], role, "approved", "Approved by the test.")
    return co.pipeline.advance(a["project_id"])


def to_release_approval(co):
    p = co.pipeline.create_project("Library", "A small library with tests.")
    assert co.pipeline.advance(p["id"])["stage"] == "prd_approval"
    decide_next(co, "ceo")
    assert decide_next(co, "cto")["stage"] == "release_approval"
    return p


# ---- release evidence ---------------------------------------------------------------------------------------
@pytest.mark.xfail(strict=True, reason="W1-F1: legacy-unmapped coverage is recorded but not shown at the release gate")
def test_release_reviewer_is_told_when_requirements_are_unmapped(co):
    p = to_release_approval(co)
    [release] = [a for a in co.pipeline.inbox("cto") if a["kind"] == "release" and a["project_id"] == p["id"]]
    ledger = json.loads(co.db.one("SELECT report FROM verification_runs WHERE id=?",
                                  json.loads(release["payload"])["ledger_id"])["report"])
    assert ledger["coverage"] == "legacy-unmapped" and ledger["release_eligible"]   # today: eligible, unmapped
    assert "unmapped" in release["summary"].lower() or "no requirements registry" in release["summary"].lower()


def test_vault_canary_reaches_checks_but_no_stored_record(co):
    """Host checks get the project's keys by design; nothing persisted may hold the value."""
    p = to_release_approval(co)
    co.vault.set(p["id"], "SERVICE_TOKEN", CANARY, "Lucky")
    ws = co.pipeline.workspace(co.pipeline.project(p["id"]))
    contract = json.loads(ws.read_file("product.json"))
    contract["checks"].append({"id": "canary", "requirement": "Reads its key",
                               "command": f"{PY} -c \"import os; print('key', os.environ['SERVICE_TOKEN'])\""})
    ws.write_file("product.json", json.dumps(contract))
    co.db.run("UPDATE approvals SET payload=? WHERE project_id=? AND kind='architecture'",
              json.dumps({"contract": ws.read_file("product.json")}), p["id"])        # as if the CTO approved it
    report = co.pipeline._host_checks(co.pipeline.project(p["id"]), ws)
    canary_check = next(c for c in report["checks"] if c["id"] == "canary")
    assert canary_check["passed"] and "[SERVICE_TOKEN]" in canary_check["output"]
    stored = json.dumps([co.db.all(f"SELECT * FROM {t}") for t in ("verification_runs", "events", "run_events",
                                                                    "approvals", "tasks")])
    assert CANARY not in stored and CANARY not in ws.read_file("docs/VERIFICATION.json")
    assert CANARY not in ws.run_command(f"{PY} -c \"import os; print(os.environ.get('SERVICE_TOKEN'))\"")


# ---- review independence ------------------------------------------------------------------------------------
@pytest.mark.xfail(strict=True, reason="W1-S2: with no checker staffed, a task passes with zero reviews")
def test_no_task_is_done_without_an_independent_review(co):
    for agent in co.db.all("SELECT a.id FROM agents a JOIN roles r ON r.id=a.role "
                           "WHERE r.kind IN ('reviewer','qa') AND a.status!='fired'"):
        co.org.fire(agent["id"], "test: nobody left to review")
    p = co.pipeline.create_project("Library", "A small library with tests.")
    co.pipeline.advance(p["id"])
    decide_next(co, "ceo")
    decide_next(co, "cto")
    done = co.db.all("SELECT id FROM tasks WHERE project_id=? AND status='done' AND key NOT LIKE 'stage-%'", p["id"])
    assert done, "the build should have finished its tasks"
    unreviewed = [t["id"] for t in done if not co.db.one("SELECT 1 FROM reviews WHERE task_id=?", t["id"])]
    assert not unreviewed


# ---- workspace boundaries -----------------------------------------------------------------------------------
@pytest.mark.skipif(os.name == "nt", reason="creating symlinks needs extra rights on Windows")
def test_file_tools_refuse_symlinks_that_leave_the_workspace(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text(CANARY)
    ws = Workspace(tmp_path / "ws")
    (ws.root / "link.txt").symlink_to(outside / "secret.txt")
    (ws.root / "linkdir").symlink_to(outside, target_is_directory=True)
    for call in (lambda: ws.read_file("link.txt"), lambda: ws.read_file("linkdir/secret.txt"),
                 lambda: ws.write_file("linkdir/new.txt", "x"), lambda: ws.replace_in_file("link.txt", CANARY, "y"),
                 lambda: ws.list_files("linkdir")):
        with pytest.raises(ToolError):
            call()
    assert (outside / "secret.txt").read_text() == CANARY and not (outside / "new.txt").exists()


# ---- engine permissions -------------------------------------------------------------------------------------
def _argv(engine, write, run, monkeypatch):
    """The argv a CLI engine would be started with, captured with a stand-in that prints its arguments."""
    from vittics_builder.engines import run_cli
    engine = {**engine, "command": [PY, "-c", "import json,sys; print(json.dumps(sys.argv[1:]))", *engine["command"][1:]],
              "prompt": "stdin", "output": "text", "usage_pattern": None}
    return json.loads(run_cli(engine, system="s", prompt="p", cwd=None, model="", write=write, run=run, timeout=60)["text"])


def test_claude_code_reviewer_gets_bash_but_not_edit_tools(monkeypatch):
    """Recorded as-is: a reviewer may run tests (Bash) but not use Edit/Write. Bash can still write files, so
    "reviewers may not edit" is not an enforced boundary (threat-model.md)."""
    argv = _argv(BUILTIN_ENGINES["claude-code"], write=False, run=True, monkeypatch=monkeypatch)
    allowed = argv[argv.index("--allowedTools") + 1:argv.index("--disallowedTools")]
    denied = argv[argv.index("--disallowedTools") + 1:]
    assert "Bash" in allowed and not {"Edit", "Write"} & set(allowed) and {"Edit", "Write"} <= set(denied)


@pytest.mark.parametrize("name", [n for n, e in BUILTIN_ENGINES.items() if not e.get("verified")])
@pytest.mark.xfail(strict=True, reason="SEC-08: unverified adapters pass no flag for read-only roles")
def test_unverified_adapters_enforce_read_only_for_read_roles(name, monkeypatch):
    assert BUILTIN_ENGINES[name]["level_args"]["read"], f"{name}: read-only roles get the CLI's default mode"
