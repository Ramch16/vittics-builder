"""Autopilot: how hands-on the CEO and CTO want to be on a project.

Explicit per-role manual approval switches override legacy levels. ON requires
manual decisions; OFF delegates routine gates including verified sign-off and
task review. Exceptions (budgets, failures, deployments, hiring, etc.) still wait.
Unset switches preserve the existing level and role opt-ins for older projects.

  off    Step by step. Every gate waits for you (as before).
  key    Key decisions. You decide the idea, approve the plan and sign off the release; the technical
         sign-off, requirements, design and the CTO's release review are approved automatically.
  final  Final sign-off only. The idea is decided as the assessment recommends (when it recommends
         building) and the plan is approved too; you sign off the release.

Each person delegates only their own decisions. A level covers the gates of the people who chose it: when
the CEO picks "key", the CEO's gates are automatic and the CTO's still wait until the CTO picks the same
level too (and the reverse). Picking a different level starts over with just that person; "off" turns it off
for both. In the desktop app and on the command line one person acts as both, so a level covers both.

Under legacy levels only these gates are automatic, when their conditions hold. Everything else waits
for a person: the final sign-off, failures (release blocked, escalations, failed deployments), changed
acceptance checks, budgets, hiring, deployments, strategies and board reviews. A release review is only
ever created after the audits, acceptance checks and executable verification have all passed.
"""
from __future__ import annotations

import json

LEVELS = {"off": "Step by step", "key": "Key decisions", "final": "Final sign-off only"}
ROLES = ("ceo", "cto")
TITLES = {"ceo": "CEO", "cto": "CTO"}
AUTO = {"key": {"feasibility", "prd", "architecture", "release"},
        "final": {"feasibility", "idea_decision", "plan", "prd", "architecture", "release"}}
CHOICE = {"build_internal": "internal", "build_to_sell": "commercial"}


def name_from(brief: str) -> str:
    """A project name from a brief: 'Build me a customer support SaaS with login...' -> 'Customer Support SaaS'."""
    import re
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9'-]*", brief)
    skip = {"build", "me", "a", "an", "the", "make", "create", "i", "want", "need", "please", "us", "my", "our"}
    stop = {"with", "and", "that", "which", "where", "using", "to", "so", "who", "in", "on", "from", "by", "via", "for"}
    picked: list[str] = []
    for w in words:
        if w.lower() in stop and picked:
            break
        if w.lower() not in skip and w.lower() not in stop:
            picked.append(w)
        if len(picked) == 4:
            break
    picked = picked or ["New", "product"]
    keep = lambda w: w.isupper() or any(c.isupper() for c in w[1:])         # SaaS, API, iOS stay as written
    return " ".join(w if keep(w) else w.capitalize() for w in picked)[:40]


class Autopilot:
    def __init__(self, pipeline) -> None:
        self.pipeline, self.db = pipeline, pipeline.db

    def level(self, pid: int) -> str:
        row = self.db.one("SELECT autopilot FROM projects WHERE id=?", pid)
        return row["autopilot"] if row and row["autopilot"] in LEVELS else "off"

    def roles(self, pid: int) -> set[str]:
        """Whose decisions the current level may make: the people who chose it."""
        row = self.db.one("SELECT autopilot_roles FROM projects WHERE id=?", pid)
        return {r for r in (row["autopilot_roles"] if row else "").split(",") if r in ROLES}

    def approval_overrides(self, pid: int) -> dict:
        row = self.db.one('SELECT approval_overrides FROM projects WHERE id=?', pid)
        return json.loads(row['approval_overrides']) if row else {}

    def set_manual_approval(self, pid: int, role: str, required: bool, by: str) -> None:
        if role not in ROLES or type(required) is not bool:
            raise ValueError('Choose CEO or CTO and a boolean required value.')
        self.pipeline.project(pid)
        with self.db.lock:
            overrides = self.approval_overrides(pid)
            overrides[role] = required
            self.db.run('UPDATE projects SET approval_overrides=? WHERE id=?', json.dumps(overrides), pid)
        self.db.log('autopilot', f'{by} turned {TITLES[role]} manual approvals '
                    + ('ON.' if required else 'OFF: routine approvals and verified final sign-off are automatic.'),
                    pid, actor=by)

    def set(self, pid: int, level: str, by: str, roles=ROLES) -> None:
        """`roles`: whose gates `by` may hand to autopilot. The dashboard passes only the signed-in person's role;
        the desktop app and the command line, where one person is both, pass both."""
        if level not in LEVELS:
            raise ValueError(f"Autopilot is one of: {', '.join(LEVELS)}.")
        roles = set(roles)
        if not roles or roles - set(ROLES):
            raise ValueError("Autopilot is chosen by the CEO, the CTO or both.")
        self.pipeline.project(pid)
        if level == "off":
            covered: set[str] = set()
        elif level == self.level(pid):
            covered = self.roles(pid) | roles           # the other person joins the level already chosen
        else:
            covered = roles                             # a new level starts with whoever chose it
        self.db.run("UPDATE projects SET autopilot=?, autopilot_roles=? WHERE id=?",
                    level, ",".join(r for r in ROLES if r in covered), pid)
        whose = "" if level == "off" or covered == set(ROLES) else \
            f" for the {TITLES[next(iter(covered))]}'s decisions only"
        self.db.log("autopilot", f"{by} set autopilot to {LEVELS[level]}{whose}.", pid, actor=by)

    def _verdict(self, approval: dict) -> tuple[bool, str, str]:
        """(may decide, choice, reason) for one pending approval."""
        payload = json.loads(approval["payload"] or "{}")
        kind = approval["kind"]
        if kind in ("feasibility", "idea_decision"):
            a = payload.get("assessment") or {}
            if a.get("feasibility") == "not_achievable":
                return False, "", "the assessment says it is not achievable"
            if kind == "idea_decision":
                choice = CHOICE.get(a.get("recommendation"))
                if not choice:
                    return False, "", "the assessment does not recommend building it"
                return True, choice, f"the assessment recommends building it ({choice})"
            return True, "", "the technical assessment finds it achievable"
        if kind in ("release", "signoff", "task_review"):
            if payload.get("inconclusive"):
                return False, "", "an audit gave no verdict"
            return True, "", "audits, acceptance checks and executable verification all passed"
        return True, "", "within the approved plan"

    def step(self, pid: int) -> bool:
        """Decide one pending gate this project's level allows. True if it decided one."""
        allowed = AUTO.get(self.level(pid), set())
        overrides = self.approval_overrides(pid)
        if not allowed and False not in overrides.values():
            return False
        covered = self.roles(pid)
        for approval in self.db.all("SELECT * FROM approvals WHERE project_id=? AND status='pending' ORDER BY id", pid):
            override = overrides.get(approval['required_role'])
            if override is True:
                continue
            routine = AUTO['final'] | {'signoff', 'task_review'}
            if override is False:
                if approval['kind'] not in routine:
                    continue
            elif approval["kind"] not in allowed:
                continue
            if override is not False and approval["required_role"] not in covered:
                who = TITLES[approval["required_role"]]
                note = f"Left for the {who}: {approval['title']} (autopilot covers only the decisions of whoever chose it)."
                if not self.db.one("SELECT 1 FROM events WHERE project_id=? AND kind='autopilot' AND message=?", pid, note):
                    self.db.log("autopilot", note, pid, actor="Autopilot")
                continue
            ok, choice, reason = self._verdict(approval)
            if not ok:
                note = f"Left for you: {approval['title']} ({reason})."
                if not self.db.one("SELECT 1 FROM events WHERE project_id=? AND kind='autopilot' AND message=?", pid, note):
                    self.db.log("autopilot", note, pid, actor="Autopilot")
                continue
            self.pipeline.decide(approval["id"], approval["required_role"], "approved",
                                 f"Approved by autopilot: {reason}.", choice=choice, autopilot=True)
            return True
        return False
