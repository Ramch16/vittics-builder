"""A project that stops must say so: limits and other stops reach the CTO as decisions, nothing is retried
while one waits, failed tickets always escalate, and runs a closed app left behind are not ghosts."""
import os
import subprocess
import sys

import pytest

from vittics_builder.costs import record_usage, summary
from vittics_builder.limits import project_limit
from vittics_builder.pipeline import PipelineError, ProjectLimit
from test_parallel import plan_approved


def pending(co, pid, *kinds):
    return [a for a in co.db.all("SELECT * FROM approvals WHERE project_id=? AND status='pending'", pid)
            if not kinds or a["kind"] in kinds]


def stop_with(co, monkeypatch, exc):
    def advance(pid):
        raise exc
    monkeypatch.setattr(co.pipeline, "_advance", advance)


def test_repair_limit_is_a_decision_not_a_silent_stop(co, monkeypatch):
    p = co.pipeline.create_project("Product", "Build a library")
    stop_with(co, monkeypatch, ProjectLimit("repairs", 6, 6))
    with pytest.raises(PipelineError, match="repair limit reached"):
        co.pipeline.advance(p["id"])
    [decision] = pending(co, p["id"], "limit")
    assert decision["required_role"] == "cto" and "repairs allowance (6/6)" in decision["title"]
    assert "Approve to allow 3 more repairs" in decision["summary"]
    errors = co.db.all("SELECT * FROM events WHERE project_id=? AND kind='error'", p["id"])
    assert not errors                                           # a limit is a decision, not an error line


def test_a_waiting_decision_is_not_retried_or_repeated(co, monkeypatch):
    p = co.pipeline.create_project("Product", "Build a library")
    stop_with(co, monkeypatch, ProjectLimit("runs", 150, 150))
    with pytest.raises(PipelineError):
        co.pipeline.advance(p["id"])
    calls = []
    monkeypatch.setattr(co.pipeline, "_advance", lambda pid: calls.append(pid))
    for _ in range(3):
        co.pipeline.advance(p["id"])                            # as a dashboard retry or Resume click would
    assert calls == [] and len(pending(co, p["id"], "limit")) == 1


def test_approving_a_limit_raises_it_for_that_project_only(co, monkeypatch):
    p = co.pipeline.create_project("Product", "Build a library")
    other = co.pipeline.create_project("Other", "Another")
    assert project_limit(co.db, co.s, p["id"], "repairs") == 6          # the standard default
    stop_with(co, monkeypatch, ProjectLimit("repairs", 6, 6))
    with pytest.raises(PipelineError):
        co.pipeline.advance(p["id"])
    [decision] = pending(co, p["id"], "limit")
    co.pipeline.decide(decision["id"], "cto", "approved")
    assert project_limit(co.db, co.s, p["id"], "repairs") == 9          # used 6 + 3 more
    assert project_limit(co.db, co.s, other["id"], "repairs") == 6      # nobody else's limit moved
    assert not pending(co, p["id"])


def test_rejecting_a_limit_pauses_the_project_without_asking_for_a_reason(co, monkeypatch):
    p = co.pipeline.create_project("Product", "Build a library")
    stop_with(co, monkeypatch, ProjectLimit("runs", 150, 150))
    with pytest.raises(PipelineError):
        co.pipeline.advance(p["id"])
    [decision] = pending(co, p["id"], "limit")
    co.pipeline.decide(decision["id"], "cto", "rejected")
    assert co.pipeline.project(p["id"])["stage"] == "paused"


def test_any_other_stop_reaches_the_cto_too(co, monkeypatch):
    p = co.pipeline.create_project("Product", "Build a library")
    stop_with(co, monkeypatch, PipelineError("Nobody on staff can take task 'core'. Hire a builder."))
    with pytest.raises(PipelineError):
        co.pipeline.advance(p["id"])
    [decision] = pending(co, p["id"], "attention")
    assert "Nobody on staff" in decision["summary"] and "stopped and needs you" in decision["title"]
    co.pipeline.decide(decision["id"], "cto", "approved")               # dealt with: try again
    assert not pending(co, p["id"])


def test_a_failed_ticket_with_no_escalation_is_escalated(co):
    p = plan_approved(co)
    lost = co.tickets.create(p["id"], "Fix the thing", "It broke", "Lucky", status="todo", role="backend_engineer")
    co.db.run("UPDATE tasks SET status='failed', attempts=3, feedback='Reviewer said no' WHERE id=?", lost["id"])
    assert not pending(co, p["id"], "escalation")
    assert co.pipeline.advance(p["id"])["stage"] == "escalation"        # not "tasks cannot start"
    [decision] = pending(co, p["id"], "escalation")
    assert "Fix the thing" in decision["title"] and "Reviewer said no" in decision["summary"]
    co.pipeline.advance(p["id"])                                        # again: still one decision
    assert len(pending(co, p["id"], "escalation")) == 1


def test_runs_a_dead_process_left_running_are_stopped(co):
    agent = co.org.agent("Ram")
    mine = co.runs.start(agent, None, None, "chat", "Hi")
    ghost = co.runs.start(agent, None, None, "chat", "Hi")
    old = co.runs.start(agent, None, None, "chat", "Hi")
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    co.db.run("UPDATE runs SET owner_pid=? WHERE id=?", dead.pid, ghost)               # its app has exited
    co.db.run("UPDATE runs SET owner_pid=NULL, started_at='2020-01-01T00:00:00+00:00' WHERE id=?", old)   # from before pids
    assert co.runs.reap() == 2
    status = {r["id"]: r["status"] for r in co.db.all("SELECT id, status FROM runs")}
    assert status[mine] == "running" and status[ghost] == "stopped" and status[old] == "stopped"
    assert co.db.one("SELECT 1 FROM run_events WHERE run_id=? AND body LIKE 'Interrupted%'", ghost)
    assert os.getpid() != dead.pid and co.runs.reap() == 0


def test_the_ledger_separates_cached_from_fresh_input(co):
    agent = co.org.agent("Ram")
    p = co.pipeline.create_project("Product", "Build a library")
    record_usage(co.db, co.s, agent, p["id"], 1_000_000, 5_000, "builder via claude-code", cost=0.0,
                 cached_tokens=900_000)
    record_usage(co.db, co.s, agent, p["id"], 10_000, 100, "builder via codex", cost=0.0)
    total = summary(co.db)["total"]
    assert (total["input_tokens"], total["cached_tokens"]) == (1_010_000, 900_000)
    [row] = [r for r in summary(co.db)["projects"] if r["id"] == p["id"]]
    assert row["cached_tokens"] == 900_000 and row["calls"] == 2


def test_alive_tells_a_running_process_from_a_finished_one_and_never_signals_it():
    from vittics_builder.runs import _alive
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        assert _alive(os.getpid()) and _alive(child.pid)
        assert child.poll() is None                      # asking did not harm it (os.kill(pid, 0) ends it on Windows)
    finally:
        child.kill()
        child.wait()
    assert not _alive(child.pid)


def test_the_reaper_leaves_runs_of_another_live_process_alone(co):
    agent = co.org.agent("Ram")
    other = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])    # e.g. the desktop app's backend
    try:
        run = co.runs.start(agent, None, None, "chat", "Hi")
        co.db.run("UPDATE runs SET owner_pid=? WHERE id=?", other.pid, run)
        assert co.runs.reap() == 0
        assert co.db.one("SELECT status FROM runs WHERE id=?", run)["status"] == "running"
        assert other.poll() is None                      # and the process itself is still running
    finally:
        other.kill()
        other.wait()
