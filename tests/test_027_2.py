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
