"""Wires the pieces together. `Company` is the one object the CLI and server use."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from .agent import AgentRuntime
from .chat import Chat
from .feedback import Feedback
from .reports import Reports
from .config import ensure_org_file, load_settings, resolve_root
from .db import DB
from .llm import RoutingProvider, make_provider
from .integrations import Integrations
from .memory import Memory
from .failover import Failover
from .machine import Machine
from .nodes import Nodes
from .platforms import rmtree_force
from .preview import Previews
from .vault import Vault
from .ai import AI
from .production import Production
from .routing import ModelRouter
from .operations_store import initialize
from .learning import Learning
from .observability import Observability
from .workers import Workers
from .arena import Arena
from .assessments import Assessments
from .marketplace import Marketplace
from .federation import Federation
from .security import Security
from .swarms import Swarms
from .runs import Runs
from .skills import Skills
from .naming import make_namer
from .org import Org
from .performance import Performance
from .pipeline import Pipeline
from .tickets import Tickets


class _LazyProvider:
    """Creates the real provider on first use, so org and status commands work without an API key."""

    def __init__(self, name: str) -> None:
        self._name, self._real = name, None

    def complete(self, **kwargs):
        if self._real is None:
            self._real = make_provider(self._name)
        return self._real.complete(**kwargs)


class Company:
    def __init__(self, root: str | os.PathLike | None = None, provider=None, create: bool = False) -> None:
        root = resolve_root(root)
        if create:
            ensure_org_file(root)
        self.s = load_settings(root)
        if not create and not self.s.db_path.exists():
            raise SystemExit(f"No company found in {root}. Run `vittics-builder init` there first.")
        self.db = DB(self.s.db_path)
        initialize(self.db)
        self.org = Org(self.db, self.s)
        self.perf = Performance(self.db, self.s, self.org)
        self.runtime = AgentRuntime(self.db, self.s, self.org,
                                    RoutingProvider(provider or _LazyProvider(self.s.provider), self.s.endpoints))
        self.pipeline = Pipeline(self.db, self.s, self.org, self.perf, self.runtime)
        self.learning = Learning(self)
        self.runtime.learning = self.learning
        self.router = ModelRouter(self.db, self.s)
        self.router.learning = self.learning
        self.runtime.router = self.router
        self.failover = Failover(self.db, self.s, self.router)
        self.runtime.failover = self.failover
        self.runtime.integrations = Integrations(self.s)
        self.swarms = Swarms(self.db, self.s, self.org)
        self.pipeline.swarms = self.swarms
        self.tickets = Tickets(self.db, self.pipeline)
        self.runtime.tickets = self.tickets
        self.memory = Memory(self.db)
        self.runtime.memory = self.memory
        self.runs = Runs(self.db)
        self.runs.reap()                      # runs a closed or crashed app left marked as running
        self.runtime.runs = self.runs
        self.skills = Skills(self.s)
        self.runtime.skills = self.skills
        self.org.namer = make_namer(self.db, self.s, self.runtime.provider)
        self.chat = Chat(self)
        self.tickets.on_human_note = self.chat.ticket_note
        self.reports = Reports(self)
        self.pipeline.reporter = self.reports.write
        self.feedback = Feedback(self)
        self.observability = Observability(self)
        self.workers = Workers(self)
        self.production = Production(self)
        self.machine = Machine(self)
        self._reroot_workspaces()
        self.nodes = Nodes(self)
        self.vault = Vault(self)
        self.ai = AI(self)
        self.runtime.vault = self.vault
        self.previews = Previews(self)
        self.runtime.nodes = self.nodes
        self.pipeline.machine = self.machine
        self.pipeline.production = self.production
        self.arena = Arena(self)
        self.assessments = Assessments(self)
        self.marketplace = Marketplace(self)
        self.federation = Federation(self)
        self.security = Security(self)
        if create:
            self.org.seed()

    def can_manage(self, role: str, agent: dict) -> bool:
        """The CEO manages everyone. The CTO manages departments that report to the CTO."""
        return role == "ceo" or self.org.boss_of(agent) == "cto"

    def events(self, limit: int = 50, project_id: int | None = None) -> list[dict]:
        if project_id:
            rows = self.db.all("SELECT * FROM events WHERE project_id=? ORDER BY id DESC LIMIT ?", project_id, limit)
        else:
            rows = self.db.all("SELECT * FROM events ORDER BY id DESC LIMIT ?", limit)
        return rows[::-1]

    def delete_project(self, pid: int, by: str) -> dict:
        """Permanently remove a project: its tickets, runs, decisions, memories and costs, its keys and preview,
        and its folders. Agents, departments and settings stay. This cannot be undone."""
        from .pipeline import PipelineError
        project = self.pipeline.project(pid)
        if self.pipeline.running(pid):
            raise PipelineError(f"{project['name']} is working right now. Pause it and wait for the work in progress "
                                "to finish before removing it.")
        self.previews.stop(pid, by)
        removed: dict[str, int] = {}
        with self.db.lock:
            self.db.conn.execute("BEGIN IMMEDIATE")          # all of it or none of it
            try:
                self._remove_project_rows(pid, removed)
                self.db.conn.execute("COMMIT")
            except BaseException:
                self.db.conn.execute("ROLLBACK")
                raise
        self.vault.erase(pid)                     # after the rows: a failure above must not lose a surviving project's keys
        if "memory_search" in {r["name"] for r in self.db.conn.execute("SELECT name FROM sqlite_master")}:
            self.db.conn.execute("INSERT INTO memory_search(memory_search) VALUES ('rebuild')")
        folders = [Path(project["workspace"])] if project["workspace"] else []
        for parent, pattern in ((self.s.workspaces / ".worktrees", f"{pid:03d}-*"),
                                (self.s.workspaces / ".previews", f"{pid}-*")):
            folders += sorted(parent.glob(pattern)) if parent.is_dir() else []
        root = self.s.workspaces.resolve()
        for folder in folders:                  # only ever inside this company's workspaces folder
            if folder.exists() and root in folder.resolve().parents:
                rmtree_force(folder)
        self.db.log("project", f"{by} removed the project {project['name']} permanently.", None, actor=by)
        return {"name": project["name"], "removed": {t: n for t, n in removed.items() if n}}

    def _remove_project_rows(self, pid: int, removed: dict) -> None:
        db = self.db
        tables = {r["name"]: {c["name"] for c in db.conn.execute(f"PRAGMA table_info({r['name']})")}
                  for r in db.conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE "
                                           "'sqlite_%' AND name NOT LIKE 'memory_search%'").fetchall()}
        tasks = [r["id"] for r in db.conn.execute("SELECT id FROM tasks WHERE project_id=?", (pid,))]
        runs = [r["id"] for r in db.conn.execute("SELECT id FROM runs WHERE project_id=?", (pid,))]

        def drop(table: str, where: str, args: tuple) -> None:
            removed[table] = removed.get(table, 0) + db.conn.execute(f"DELETE FROM {table} WHERE {where}", args).rowcount
        for start in range(0, len(tasks), 500):
            part = tasks[start:start + 500]
            drop("ticket_comments", f"task_id IN ({','.join('?' * len(part))})", tuple(part))
        for start in range(0, len(runs), 500):
            part = runs[start:start + 500]
            for table in ("run_events", "steers"):
                if table in tables:
                    drop(table, f"run_id IN ({','.join('?' * len(part))})", tuple(part))
        for table, columns in tables.items():
            if table != "projects" and "project_id" in columns:
                drop(table, "project_id=?", (pid,))
        drop("projects", "id=?", (pid,))

    def _reroot_workspaces(self) -> None:
        """Projects whose saved workspace path is gone, but whose folder is in this company's workspaces/
        (the company was moved, or renamed from OrgForge), point at the folder that is here."""
        for p in self.db.all("SELECT id, workspace FROM projects WHERE workspace!=''"):
            saved = Path(p["workspace"])
            here = self.s.workspaces / saved.name
            if not saved.exists() and here.is_dir() and here != saved:
                self.db.run("UPDATE projects SET workspace=? WHERE id=?", str(here), p["id"])
                self.db.log("project", f"Workspace found at {here} (was {saved}).", p["id"])
