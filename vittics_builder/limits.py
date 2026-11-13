"""Project allowances: how many repair launches and agent runs a project may use before a person looks at it.

A limit is a guard against a runaway loop, not a target. When one is reached the project does not stop quietly:
the CTO gets a decision (raise it and carry on, or pause the project). The CTO's choice is stored on the
project, so org.yaml does not have to be edited and Vittics Builder restarted.
"""
from __future__ import annotations

# Sized from real pilots: a one-page tool used about 110 runs, a small web app about 140.
DEFAULT_REPAIRS = {"small": 2, "standard": 6}
DEFAULT_RUNS = {"small": 60, "standard": 150}
RAISE_BY = {"repairs": 3, "runs": 50}
NAMES = {"repairs": "repairs", "runs": "agent runs"}
SETTINGS = {"repairs": "max_project_repairs", "runs": "max_project_runs"}
COLUMNS = {"repairs": "repair_cap", "runs": "run_cap"}


def reached(which: str, used: int, limit: int) -> str:
    return (f"Project {'repair' if which == 'repairs' else 'agent-run'} limit reached ({used}/{limit}). "
            f"No {'builder' if which == 'repairs' else 'agent'} was launched. Work is preserved.")


def project_limit(db, settings, project_id: int, which: str) -> int | None:
    """The limit that applies to a project, or None for no limit. A raised project limit wins over the
    company default; `pipeline.max_project_*: null` in org.yaml turns the limit off for every project."""
    pipeline = (settings.raw.get("pipeline") or {})
    key = SETTINGS[which]
    configured = pipeline.get(key, "default")
    if configured is None:
        return None
    if configured != "default" and (type(configured) is not int or configured < 0):
        raise ValueError(f"pipeline.{key} must be a nonnegative integer or null.")
    row = db.one(f"SELECT size, {COLUMNS[which]} AS cap FROM projects WHERE id=?", project_id) or {}
    if row.get("cap") is not None:
        return int(row["cap"])
    if configured != "default":
        return configured
    table = DEFAULT_REPAIRS if which == "repairs" else DEFAULT_RUNS
    return table["small" if row.get("size") == "small" else "standard"]


def raise_limit(db, project_id: int, which: str, used: int) -> int:
    """Allow `RAISE_BY[which]` more beyond what is used now. Returns the new limit."""
    new = used + RAISE_BY[which]
    db.run(f"UPDATE projects SET {COLUMNS[which]}=? WHERE id=?", new, project_id)
    return new
