"""0.27.2: no agent left working after the app quits, reviewers are not marked wrong for what only a person could
check, and work starts again by itself after a usage limit."""
import os
import subprocess
import sys
import threading

import pytest

from vittics_builder.engines import EngineUnavailable
from vittics_builder.platforms import kill_descendants, pid_alive
from vittics_builder.pipeline import PipelineError
from test_parallel import plan_approved


def test_pid_alive_is_shared_and_never_harms_the_process():
    from vittics_builder import preview, runs
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        assert pid_alive(os.getpid()) and pid_alive(child.pid) and not pid_alive(None) and not pid_alive(0)
        assert runs._alive(child.pid) and preview.alive(child.pid)
        assert child.poll() is None
    finally:
        child.kill()
        child.wait()
    assert not pid_alive(child.pid)


def test_quitting_stops_the_agents_the_app_started():
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    grandchild_parent = subprocess.Popen([sys.executable, "-c",
        "import subprocess, sys, time; subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); time.sleep(60)"])
    try:
        assert kill_descendants() >= 2
        child.wait(timeout=10)
        grandchild_parent.wait(timeout=10)
        assert child.returncode is not None and grandchild_parent.returncode is not None
    finally:
        for p in (child, grandchild_parent):
            if p.poll() is None:
                p.kill()


def test_a_reviewer_who_only_asked_for_human_evidence_is_not_marked_wrong(co):
    p = plan_approved(co)
    task = co.tickets.create(p["id"], "Core", "Build core", "Lucky", status="todo", role="backend_engineer")
    reviewer = co.org.agent("Badri")
    learning = co.runtime.learning
    if learning is None or not learning.enabled:
        pytest.skip("learning is off in this configuration")
    before = co.org.agent("Badri")["score"]
    learning.verdict(p["id"], task["id"], reviewer["id"], None, "request_changes", 60, unverifiable=True)
    learning.verdict(p["id"], task["id"], co.org.agent("Pavan")["id"], None, "request_changes", 60)
    learning.settle_task(task["id"], True, "Lucky")                    # the CTO accepted the ticket anyway
    marks = {r["name"]: r["settled_by"] for r in co.db.all(
        "SELECT a.name, v.settled_by FROM review_verdicts v JOIN agents a ON a.id=v.reviewer_id WHERE v.task_id=?", task["id"])}
    assert marks["Badri"].startswith("not judged") and not marks["Pavan"].startswith("not judged")
    assert co.org.agent("Badri")["score"] == before                    # nothing was recorded against the one who asked for evidence
    assert co.org.agent("Pavan")["score"] != before                    # a plain too-strict block still counts


def test_work_starts_again_by_itself_after_a_usage_limit(co, monkeypatch):
    p = co.pipeline.create_project("Product", "Build a library")
    started = threading.Event()
    co.pipeline.auto_resume = lambda pid: started.set()
    monkeypatch.setattr("vittics_builder.failover.reset_after", lambda message, default: 0)

    def limit(pid):
        raise EngineUnavailable("claude-code is unavailable: You've hit your limit, resets 4pm")
    monkeypatch.setattr(co.pipeline, "_advance", limit)
    with pytest.raises(PipelineError, match="Work paused"):
        co.pipeline.advance(p["id"])
    assert "automatically" in co.db.one("SELECT message FROM events WHERE kind='paused' ORDER BY id DESC")["message"]
    for timer in list(co.pipeline._auto_timers.values()):
        timer.cancel()
    co.pipeline._auto_timers.clear()
    co.pipeline._auto_tries[p["id"]] = 4                                 # four automatic tries have already failed
    with pytest.raises(PipelineError):
        co.pipeline.advance(p["id"])
    assert not co.pipeline._auto_timers                                  # so it stops and waits for a person


def test_an_expired_login_is_not_retried_automatically(co, monkeypatch):
    p = co.pipeline.create_project("Product", "Build a library")
    co.pipeline.auto_resume = lambda pid: None

    def signed_out(pid):
        raise EngineUnavailable("claude-code is unavailable: login expired. Run `claude auth login`")
    monkeypatch.setattr(co.pipeline, "_advance", signed_out)
    with pytest.raises(PipelineError):
        co.pipeline.advance(p["id"])
    assert not co.pipeline._auto_timers


def test_a_small_builder_is_told_to_work_economically(tmp_path, monkeypatch):
    from vittics_builder.company import Company
    from vittics_builder.llm import MockProvider
    from vittics_builder.pipeline import SMALL_BUILD
    asks = []
    for size in ("small", "standard"):
        co = Company(tmp_path / size, provider=MockProvider(), create=True)
        p = co.pipeline.create_project("Product", "Build a library", size=size)
        task = co.tickets.create(p["id"], "Core", "Build core", "Lucky", status="todo", role="backend_engineer")
        original = co.runtime.run

        def run(agent, instructions, workspace, _o=original, **kw):
            asks.append((size, instructions))
            return _o(agent, instructions, workspace, **kw)
        monkeypatch.setattr(co.runtime, "run", run)
        co.pipeline._run_task(p, task, co.pipeline.workspace(p))
    builders = {size: [a for s, a in asks if s == size and "Your task [" in a] for size in ("small", "standard")}
    assert builders["small"] and all(SMALL_BUILD in a for a in builders["small"])
    assert builders["standard"] and not any(SMALL_BUILD in a for a in builders["standard"])


def test_a_ticket_blocked_only_by_checks_a_person_must_do_passes_without_rework(co, monkeypatch):
    from vittics_builder.agent import RunResult
    p = co.pipeline.create_project("Product", "Build a library", size="small")
    task = co.tickets.create(p["id"], "Core", "Build core", "Lucky", status="todo", role="backend_engineer")
    original, reviews = co.runtime.run, []

    def run(agent, instructions, workspace, **kw):
        if (kw.get("meta") or {}).get("author"):
            reviews.append(1)
            return RunResult(completed=True, review={"score": 88, "verdict": "request_changes", "blocker_type": "verification",
                "notes": "Open the app in a browser and click through the flows.",
                "acceptance": [{"criterion": "Manual click-through", "status": "unverified", "evidence": "No browser"}]})
        return original(agent, instructions, workspace, **kw)
    monkeypatch.setattr(co.runtime, "run", run)
    assert co.pipeline._run_task(p, task, co.pipeline.workspace(p))
    row = co.db.one("SELECT status, attempts FROM tasks WHERE id=?", task["id"])
    assert (row["status"], row["attempts"]) == ("done", 0) and reviews          # no send-back, no second build
    assert co.db.one("SELECT 1 FROM ticket_comments WHERE task_id=? AND body LIKE '%Not checked by a person%'", task["id"])


def test_a_ticket_with_a_real_defect_is_still_sent_back(co, monkeypatch):
    from vittics_builder.agent import RunResult
    p = co.pipeline.create_project("Product", "Build a library", size="small")
    task = co.tickets.create(p["id"], "Core", "Build core", "Lucky", status="todo", role="backend_engineer")
    original = co.runtime.run

    def run(agent, instructions, workspace, **kw):
        if (kw.get("meta") or {}).get("author"):
            return RunResult(completed=True, review={"score": 40, "verdict": "request_changes", "blocker_type": "defect",
                "notes": "Delete does nothing."})
        return original(agent, instructions, workspace, **kw)
    monkeypatch.setattr(co.runtime, "run", run)
    co.pipeline._run_task(p, task, co.pipeline.workspace(p))
    assert co.db.one("SELECT attempts FROM tasks WHERE id=?", task["id"])["attempts"] >= 1


def test_a_small_project_does_not_build_tickets_agents_file_on_their_own(co):
    small = co.pipeline.create_project("Tiny", "A checklist", size="small")
    big = co.pipeline.create_project("Big", "A product")
    for p in (small, big):
        co.db.run("UPDATE projects SET stage='build' WHERE id=?", p["id"])
    agent = co.org.agent("Pavan")

    def file(pid, **extra):
        result = type("R", (), {"filed": []})()
        co.tickets.agent_tool(agent, "create_ticket", {"title": "Manually verify the browser flow", "description": "Click through it",
                                                       "role": "qa_engineer", **extra}, pid, None, result)
        return co.db.one("SELECT status FROM tasks WHERE id=?", int(result.filed[0].split("-")[1]))["status"]
    assert file(small["id"]) == "backlog" and file(big["id"]) == "todo"
    assert file(small["id"], title="x", type="bug", priority="urgent") == "todo"      # a real urgent bug is still built


def test_a_small_project_is_not_stopped_by_a_missing_second_qa(co, monkeypatch):
    from vittics_builder.agent import RunResult
    p = co.pipeline.create_project("Tiny", "A checklist", size="small")
    task = co.tickets.create(p["id"], "Verify", "Check it", "Lucky", status="todo", role="qa_engineer")
    original = co.runtime.run
    monkeypatch.setattr(co.pipeline, "_checkers", lambda *a, **k: [co.org.role("qa_engineer"), co.org.role("code_reviewer")]
                        if hasattr(co.org, "role") else [])

    def run(agent, instructions, workspace, **kw):
        if (kw.get("meta") or {}).get("author"):
            return RunResult(completed=True, review={"score": 90, "verdict": "approve", "notes": "ok"})
        return original(agent, instructions, workspace, **kw)
    monkeypatch.setattr(co.runtime, "run", run)
    if not hasattr(co.org, "role"):
        import pytest
        pytest.skip("no role lookup to build the scenario")
    only_qa = co.org.pick(role="qa_engineer")
    assert co.pipeline._run_task(p, task, co.pipeline.workspace(p))


def test_a_small_project_goes_on_when_only_human_checks_are_left(co, monkeypatch):
    from vittics_builder.agent import RunResult
    from test_pipeline import decide_next
    original = co.runtime.run

    def run(agent, *args, **kwargs):
        if (kwargs.get("meta") or {}).get("purpose") == "integration":
            return RunResult(completed=True, review={"score": 85, "verdict": "request_changes", "blocker_type": "verification",
                "notes": "No browser here.", "acceptance": [{"criterion": "Click through in a browser", "status": "unverified", "evidence": "no browser"}]})
        return original(agent, *args, **kwargs)
    monkeypatch.setattr(co.runtime, "run", run)
    p = co.pipeline.create_project("Tiny", "Build a library", size="small")
    co.pipeline.advance(p["id"])
    decide_next(co, "ceo")
    result = decide_next(co, "cto")
    assert result["stage"] != "release_blocked"
    assert not [a for a in co.pipeline.inbox("cto") if a["kind"] == "release_blocked"]


def test_a_small_project_status_report_is_its_facts_with_no_agent_call(co, monkeypatch):
    p = co.pipeline.create_project("Tiny", "A checklist", size="small")
    seen = []
    orig = co.runtime.run
    monkeypatch.setattr(co.runtime, "run", lambda *a, **k: seen.append((k.get("meta") or {}).get("purpose")) or orig(*a, **k))
    co.reports.request(p["id"], "Test")
    report = co.db.one("SELECT * FROM reports WHERE project_id=? ORDER BY id DESC", p["id"])
    co.reports.write(report)
    assert "status_report" not in seen
    assert co.reports.latest(p["id"])[0]["body"]


def _fake_cli(co, monkeypatch, who):
    from vittics_builder.engines import BUILTIN_ENGINES
    co.s.engines["fake"] = {**BUILTIN_ENGINES["claude-code"], "command": ["fake"], "output": "text"}
    co.db.run("UPDATE agents SET model='cli:fake' WHERE name=?", who)
    seen = []

    def cli(engine, **kw):
        seen.append(kw.get("session"))
        return dict(text="done", is_error=False, turns=1, cost=0, input_tokens=0, output_tokens=0)
    monkeypatch.setattr("vittics_builder.agent.run_cli", cli)
    return seen


def test_a_builder_sent_back_on_the_same_ticket_continues_its_conversation(co, monkeypatch):
    p = co.pipeline.create_project("Tiny", "A checklist", size="small")
    builder = co.org.pick(kind="builder")
    seen = _fake_cli(co, monkeypatch, builder["name"])
    agent = co.org.agent(builder["name"])
    ws = co.pipeline.workspace(p)
    co.runtime.run(agent, "Build", ws, project_id=p["id"], meta={"ticket_id": 7})
    co.runtime.run(agent, "Fix the findings", ws, project_id=p["id"], meta={"ticket_id": 7})
    co.runtime.run(agent, "Another ticket", ws, project_id=p["id"], meta={"ticket_id": 8})
    assert seen[0][0] == "new" and seen[1] == ("resume", seen[0][1])
    assert seen[2][0] == "new" and seen[2][1] != seen[0][1]


def test_a_reviewer_never_continues_an_earlier_conversation(co, monkeypatch):
    p = co.pipeline.create_project("Tiny", "A checklist", size="small")
    reviewer = co.org.pick(kind="reviewer")
    seen = _fake_cli(co, monkeypatch, reviewer["name"])
    agent = co.org.agent(reviewer["name"])
    for _ in range(2):
        co.runtime.run(agent, "Review", co.pipeline.workspace(p), project_id=p["id"], meta={"ticket_id": 7})
    assert seen == [None, None]


def test_claude_keeps_its_session_only_when_asked_to():
    from vittics_builder import engines
    seen = []

    class Done:
        returncode, stderr = 0, ""
        stdout = '{"result": "ok", "usage": {}, "num_turns": 1}'
    engine = engines.BUILTIN_ENGINES["claude-code"]
    import subprocess
    orig = engines.subprocess.run
    engines.subprocess.run = lambda argv, **kw: (seen.append(argv), Done())[1]
    try:
        engines.run_cli(engine, system="s", prompt="p", cwd=None, model="", write=False, run=False, timeout=5)
        engines.run_cli(engine, system="s", prompt="p", cwd=None, model="", write=False, run=False, timeout=5, session=("new", "abc"))
        engines.run_cli(engine, system="s", prompt="p", cwd=None, model="", write=False, run=False, timeout=5, session=("resume", "abc"))
    finally:
        engines.subprocess.run = orig
    assert "--no-session-persistence" in seen[0] and "--resume" not in seen[0]
    assert "--no-session-persistence" not in seen[1] and seen[1][seen[1].index("--session-id") + 1] == "abc"
    assert "--no-session-persistence" not in seen[2] and seen[2][seen[2].index("--resume") + 1] == "abc"


def _asks_for(tmp_path, monkeypatch, size):
    from vittics_builder.company import Company
    from vittics_builder.llm import MockProvider
    from test_pipeline import decide_next
    co = Company(tmp_path / size, provider=MockProvider(), create=True)
    co.s.screenshots = False
    asks = []
    original = co.runtime.run

    def run(agent, instructions, workspace, **kw):
        asks.append((kw.get("meta") or {}, instructions))
        return original(agent, instructions, workspace, **kw)
    monkeypatch.setattr(co.runtime, "run", run)
    p = co.pipeline.create_project("Product", "Build a library", size=size)
    co.pipeline.advance(p["id"])
    decide_next(co, "ceo")
    decide_next(co, "cto")
    return [a for _, a in asks], [(m, a) for m, a in asks]


def test_ticket_sizing_is_for_standard_projects_and_a_small_one_builds_one_ticket(tmp_path, monkeypatch):
    from vittics_builder.pipeline import TICKET_SIZE, VISUAL_DIRECTION, APPLY_DIRECTION
    for size in ("small", "standard"):
        asks, _ = _asks_for(tmp_path, monkeypatch, size)
        assert any(TICKET_SIZE in a for a in asks) == (size == "standard"), size
        assert any("plan one build ticket" in a or "one build ticket for the app" in a for a in asks) == (size == "small"), size
        assert any(VISUAL_DIRECTION in a for a in asks), size              # the visual direction is for every size
        assert any(APPLY_DIRECTION in a for a in asks), size


def test_only_a_small_projects_release_qa_gets_a_one_pass_cap(tmp_path, monkeypatch):
    from vittics_builder.pipeline import SMALL_QA
    for size in ("small", "standard"):
        _, pairs = _asks_for(tmp_path / "q", monkeypatch, size)
        qa = [(m, a) for m, a in pairs if m.get("purpose") == "integration"]
        assert qa, size
        assert all((SMALL_QA in a) == (size == "small") for _, a in qa)
        assert all((m.get("max_turns") == 20) == (size == "small") for m, _ in qa)


def test_screenshots_are_taken_outside_git_and_skipped_without_a_browser(co, monkeypatch):
    import shutil
    p = co.pipeline.create_project("Shots", "A page", size="small")
    ws = co.pipeline.workspace(p)
    ws.write_file("index.html", "<html><body><h1>Hello</h1></body></html>")
    ws.commit("page")
    assert co.pipeline._screenshots(p, ws) is False                     # off in tests
    co.s.screenshots = True
    monkeypatch.setattr(shutil, "which", lambda n: None)
    monkeypatch.setattr("vittics_builder.pipeline.Path.is_file", lambda self: self.name == "index.html")
    assert co.pipeline._screenshots(p, ws) is False                     # no browser installed


def test_work_a_restart_cut_off_carries_on_by_itself(co, monkeypatch):
    from fastapi.testclient import TestClient
    from vittics_builder.server import create_app
    p = co.pipeline.create_project("Tiny", "A checklist", size="small")
    other = co.pipeline.create_project("Paused", "Another", size="small")
    agent = co.org.pick(kind="builder")
    for pid in (p["id"], other["id"]):
        co.db.run("INSERT INTO runs (agent_id, project_id, purpose, status, started_at, owner_pid) VALUES (?,?,?,?,?,?)",
                  agent["id"], pid, "builder", "running", "2026-01-01T00:00:00+00:00", 999999)
    co.db.run("UPDATE projects SET stage='paused' WHERE id=?", other["id"])
    assert co.runs.reap() == 2 and co.runs.interrupted_projects == {p["id"], other["id"]}
    advanced = []
    monkeypatch.setattr(co.pipeline, "advance", lambda pid, **k: advanced.append(pid))
    with TestClient(create_app(co, {"ceo": "c", "cto": "t"})):
        import time
        time.sleep(0.3)
    assert advanced == [p["id"]]                                       # the paused one stays paused


def test_the_phone_screenshot_uses_a_390px_frame(co, monkeypatch, tmp_path):
    import shutil
    from vittics_builder import pipeline as pl
    p = co.pipeline.create_project("Shots", "A page", size="small")
    ws = co.pipeline.workspace(p)
    ws.write_file("index.html", "<html><body>Hi</body></html>")
    ws.commit("page")
    co.s.screenshots = True
    monkeypatch.setattr(shutil, "which", lambda n: "/fake/chrome")
    targets = []

    def run(argv, **kw):
        shot = next(a for a in argv if a.startswith("--screenshot="))[len("--screenshot="):]
        targets.append((shot.rsplit("/", 1)[-1], argv[-1]))
        open(shot, "wb").write(b"png")

        class R:
            returncode = 0
        return R()
    monkeypatch.setattr(pl.subprocess, "run", run)
    assert co.pipeline._screenshots(p, ws) is True
    assert targets[0][1].endswith("index.html") and targets[1][1].endswith("phone.html")
    assert "width:390px" in (ws.root / ".shots" / "phone.html").read_text()
