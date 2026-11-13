"""Removing a project: everything it made goes, nothing else does, and it happens all at once or not at all."""
import sys
import threading
import types

import pytest
from fastapi.testclient import TestClient

from vittics_builder import buildinfo
from vittics_builder.cli import main
from vittics_builder.costs import record_usage
from vittics_builder.pipeline import PipelineError
from vittics_builder.server import create_app
from test_parallel import plan_approved


def rows(co, pid):
    """How many rows every project-owned table holds for a project, as a dict of the non-empty ones."""
    out = {}
    for t in co.db.all("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' "
                       "AND name NOT LIKE 'memory_search%'"):
        cols = {c["name"] for c in co.db.all(f"PRAGMA table_info({t['name']})")}
        if "project_id" in cols:
            n = co.db.one(f"SELECT COUNT(*) AS n FROM {t['name']} WHERE project_id=?", pid)["n"]
            if n:
                out[t["name"]] = n
    return out


def two_projects(co):
    first = plan_approved(co)
    co.pipeline.advance(first["id"])                                  # built: tickets, runs, reviews, costs, events
    second = co.pipeline.create_project("Keep me", "Another product")
    co.pipeline.advance(second["id"])
    for p in (first, second):
        record_usage(co.db, co.s, co.org.agent("Ram"), p["id"], 1000, 100, "builder via claude-code", cost=0.0)
    co.vault.set(first["id"], "STRIPE_KEY", "sk_test_123", "Niki")
    return first, second


def test_everything_the_project_made_is_removed_and_nothing_else(co):
    first, second = two_projects(co)
    keep = rows(co, second["id"])
    agents = co.db.one("SELECT COUNT(*) AS n FROM agents")["n"]
    folder = co.pipeline.workspace(first).root
    assert rows(co, first["id"]) and folder.is_dir()
    result = co.delete_project(first["id"], "Niki")
    assert result["name"] == "Product" and result["removed"]["tasks"] and result["removed"]["usage"]
    assert rows(co, first["id"]) == {}                               # no table still mentions it
    assert not co.db.one("SELECT 1 FROM ticket_comments WHERE task_id NOT IN (SELECT id FROM tasks)")
    assert not co.db.one("SELECT 1 FROM run_events WHERE run_id NOT IN (SELECT id FROM runs)")
    assert not folder.exists()
    assert co.vault.names(first["id"]) == [] and not co.vault._path(first["id"]).exists()
    assert rows(co, second["id"]) == keep                            # the other project is untouched
    assert co.db.one("SELECT COUNT(*) AS n FROM agents")["n"] == agents
    assert co.db.one("PRAGMA integrity_check")["integrity_check"] == "ok"
    assert [p["name"] for p in co.db.all("SELECT name FROM projects")] == ["Keep me"]
    assert co.db.one("SELECT 1 FROM events WHERE project_id IS NULL AND message LIKE 'Niki removed the project Product%'")


def test_a_failure_part_way_leaves_the_project_whole(co, monkeypatch):
    first, _ = two_projects(co)
    before = rows(co, first["id"])
    real = co._remove_project_rows

    def half(pid, removed):
        co.db.conn.execute("DELETE FROM usage WHERE project_id=?", (pid,))      # some of it is gone...
        raise RuntimeError("disk full")                                          # ...then it fails
    monkeypatch.setattr(co, "_remove_project_rows", half)
    with pytest.raises(RuntimeError):
        co.delete_project(first["id"], "Niki")
    assert rows(co, first["id"]) == before                           # rolled back: nothing was lost
    monkeypatch.setattr(co, "_remove_project_rows", real)
    co.delete_project(first["id"], "Niki")
    assert rows(co, first["id"]) == {}


def test_a_project_that_is_working_cannot_be_removed(co):
    first, _ = two_projects(co)
    lock = co.pipeline._locks.setdefault(first["id"], threading.Lock())
    lock.acquire()
    try:
        with pytest.raises(PipelineError, match="working right now"):
            co.delete_project(first["id"], "Niki")
    finally:
        lock.release()
    assert rows(co, first["id"])


def test_the_dashboard_api_needs_the_ceo_and_the_exact_name(co):
    first, _ = two_projects(co)
    client = TestClient(create_app(co, {"ceo": "ceo-token", "cto": "cto-token"}))
    url = f"/api/projects/{first['id']}/delete"
    assert client.post(url, json={"confirm": "Product"}, headers={"X-Token": "cto-token"}).status_code == 403
    assert client.post(url, json={"confirm": "product"}, headers={"X-Token": "ceo-token"}).status_code == 400
    assert client.post(url, json={}, headers={"X-Token": "ceo-token"}).status_code == 400
    assert rows(co, first["id"])                                      # still there after every refusal
    done = client.post(url, json={"confirm": "Product"}, headers={"X-Token": "ceo-token"})
    assert done.status_code == 200 and done.json()["name"] == "Product"
    assert rows(co, first["id"]) == {}


def test_the_command_line_needs_the_name_too(co, capsys):
    first, _ = two_projects(co)
    home = ["--home", str(co.s.root)]
    assert main([*home, "delete-project", str(first["id"]), "--yes", "wrong"]) == 1      # refused, not raised
    assert "did not match" in capsys.readouterr().err
    assert rows(co, first["id"])
    assert main([*home, "delete-project", str(first["id"]), "--yes", "Product"]) == 0
    assert "Removed Product" in capsys.readouterr().out
    assert rows(co, first["id"]) == {}


# ---- which build is this ------------------------------------------------------------------------
def test_the_build_label_names_the_commit_an_installer_was_built_from(monkeypatch):
    monkeypatch.setitem(sys.modules, "vittics_builder._build", types.SimpleNamespace(COMMIT="abc1234"))
    buildinfo.commit.cache_clear()
    try:
        assert buildinfo.label().endswith("+abc1234") and buildinfo.label().startswith("0.")
    finally:
        buildinfo.commit.cache_clear()


def test_the_dashboard_reports_the_build(co):
    state = TestClient(create_app(co, {"ceo": "ceo-token", "cto": "cto-token"})).get(
        "/api/state", headers={"X-Token": "ceo-token"}).json()
    assert state["build"].startswith(state["version"])


def test_a_source_checkouts_commit_is_read_from_git_without_running_git(tmp_path, monkeypatch):
    import subprocess as sp

    def no_git(*args, **kwargs):
        raise AssertionError("git must not be run to build the label")
    monkeypatch.setattr(sp, "run", no_git)
    git = tmp_path / ".git"
    (git / "refs" / "heads").mkdir(parents=True)
    (git / "HEAD").write_text("ref: refs/heads/main\n")
    (git / "refs" / "heads" / "main").write_text("0123456789abcdef0123456789abcdef01234567\n")
    assert buildinfo.git_commit(tmp_path) == "0123456"
    (git / "refs" / "heads" / "main").unlink()                              # a packed ref
    (git / "packed-refs").write_text("# pack-refs\nfedcba9876543210fedcba9876543210fedcba98 refs/heads/main\n")
    assert buildinfo.git_commit(tmp_path) == "fedcba9"
    (git / "HEAD").write_text("89abcdef0123456789abcdef0123456789abcdef\n")  # detached
    assert buildinfo.git_commit(tmp_path) == "89abcde"
    assert buildinfo.git_commit(tmp_path / "nowhere") == ""


def test_folders_with_read_only_files_are_removed(tmp_path):
    import os
    import stat
    from vittics_builder.platforms import rmtree_force
    folder = tmp_path / "workspace" / ".git" / "objects"
    folder.mkdir(parents=True)
    locked = folder / "pack"
    locked.write_text("x")
    os.chmod(locked, stat.S_IREAD)                                          # git makes its objects read-only
    rmtree_force(tmp_path / "workspace")
    assert not (tmp_path / "workspace").exists()
