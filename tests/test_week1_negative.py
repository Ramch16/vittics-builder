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
def test_no_task_is_done_without_an_independent_review(co):
    """A-01 (W1-F2/W1-S2), decision D1/D2: with nobody left to review, tickets stay open and the build stops
    with a resumable error instead of marking work done with zero reviews."""
    for agent in co.db.all("SELECT a.id FROM agents a JOIN roles r ON r.id=a.role "
                           "WHERE r.kind IN ('reviewer','qa') AND a.status!='fired'"):
        co.org.fire(agent["id"], "test: nobody left to review")
    p = co.pipeline.create_project("Library", "A small library with tests.")
    co.pipeline.advance(p["id"])
    decide_next(co, "ceo")
    from vittics_builder.pipeline import PipelineError
    with pytest.raises(PipelineError, match="independent review"):
        decide_next(co, "cto")
    built = co.db.all("SELECT id, status FROM tasks WHERE project_id=? AND key NOT LIKE 'stage-%'", p["id"])
    assert built, "the plan should have produced tasks"
    done = [t["id"] for t in built if t["status"] == "done"]
    assert not [t for t in done if not co.db.one("SELECT 1 FROM reviews WHERE task_id=?", t)]
    assert not done
    assert co.db.one("SELECT 1 FROM events WHERE project_id=? AND message LIKE '%required independent review%'", p["id"])


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


def test_claude_code_engine_maps_run_permission_to_bash(monkeypatch):
    """The engine grants Bash only when the role may run commands. Reviewer roles no longer get run_command
    (decision D4, see test_reviewer_roles_get_no_shell), so a claude-code reviewer runs with Read/Glob/Grep only;
    QA, which keeps its shell, gets Bash but not Edit/Write."""
    argv = _argv(BUILTIN_ENGINES["claude-code"], write=False, run=True, monkeypatch=monkeypatch)
    allowed = argv[argv.index("--allowedTools") + 1:argv.index("--disallowedTools")]
    denied = argv[argv.index("--disallowedTools") + 1:]
    assert "Bash" in allowed and not {"Edit", "Write"} & set(allowed) and {"Edit", "Write"} <= set(denied)


@pytest.mark.parametrize("name", [n for n, e in BUILTIN_ENGINES.items() if not e.get("verified")])
def test_unverified_adapters_refuse_read_only_roles_in_a_workspace(name, tmp_path):
    """SEC-08, decision D5: an unverified adapter with no read-only flag is refused for read-only roles in a
    project workspace, before anything starts."""
    from vittics_builder.engines import EngineError, run_cli
    engine = BUILTIN_ENGINES[name]
    if engine["level_args"]["read"]:
        pytest.skip(f"{name} now passes a read-only flag")
    with pytest.raises(EngineError, match="no verified read-only mode"):
        run_cli(engine, system="s", prompt="p", cwd=str(tmp_path), model="", write=False, run=False, timeout=5)


@pytest.mark.parametrize("name", [n for n, e in BUILTIN_ENGINES.items() if not e.get("verified")])
def test_unverified_adapters_still_build_with_their_edit_flag(name, tmp_path, monkeypatch):
    """Builders keep working on these CLIs: write roles are not refused (only read-only roles are)."""
    argv = _argv(BUILTIN_ENGINES[name], write=True, run=True, monkeypatch=monkeypatch)
    assert argv[-len(BUILTIN_ENGINES[name]["level_args"]["write"]):] == BUILTIN_ENGINES[name]["level_args"]["write"] \
        or set(BUILTIN_ENGINES[name]["level_args"]["write"]) <= set(argv)


def test_reviewer_roles_get_no_shell(co):
    """Decision D4: reviewer roles run without run_command (a shell can write files); QA keeps it."""
    captured = {}
    original = co.runtime._run_cli

    def spy(agent, role, names, *rest, **kw):
        captured[role["kind"]] = list(names)
        return original(agent, role, names, *rest, **kw)
    reviewer = co.db.one("SELECT a.* FROM agents a JOIN roles r ON r.id=a.role WHERE r.kind='reviewer' AND a.status!='fired'")
    qa = co.db.one("SELECT a.* FROM agents a JOIN roles r ON r.id=a.role WHERE r.kind='qa' AND a.status!='fired'")
    for agent in (reviewer, qa):
        co.db.run("UPDATE agents SET model='cli:missing-engine' WHERE id=?", agent["id"])
    co.runtime._run_cli = spy
    p = co.pipeline.create_project("Library", "A small library with tests.")
    ws = co.pipeline.workspace(co.pipeline.project(p["id"]))
    for agent in (reviewer, qa):
        co.runtime.run(co.db.one("SELECT * FROM agents WHERE id=?", agent["id"]), "Check it.", ws, project_id=p["id"])
    assert "run_command" not in captured["reviewer"] and "run_approved_checks" in captured["reviewer"]
    assert "run_command" in captured["qa"]
