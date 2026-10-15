"""Shared long-term memory: what the team has learned, kept across tickets and projects.

Agents save lasting facts and decisions with `remember` ("the API uses JWT in cookies",
"Niki wants British spelling everywhere"). Before each run, the memories most relevant to the
assignment, from its project and company-wide, are given to the agent.
"""
from __future__ import annotations

import re
import hashlib
import json
from pathlib import Path

from .db import DB, now

CATEGORIES = ('business', 'product', 'architecture', 'code', 'customer', 'security', 'agent', 'failure', 'decision')

MEMORY_TOOL_SPECS = {
    "remember": {
        "description": "Save a lasting fact or decision the team should know later: a convention, a choice and why, "
                       "a gotcha, a preference from the CEO or CTO. Not for progress updates (comment on the ticket).",
        "input_schema": {"type": "object", "properties": {
            "text": {"type": "string", "description": "One or two sentences"},
            "category": {"type": "string", "enum": list(CATEGORIES)},
            "source": {"type": "string", "description": "Evidence reference: document, ticket, or discussion"},
            "evidence_files": {"type": "array", "items": {"type": "string"},
                               "description": "Project-relative files supporting this fact; edits invalidate recall"},
            "scope": {"type": "string", "enum": ["project", "company"],
                      "description": "project (default) or company-wide"}}, "required": ["text"]},
    },
    "recall_memory": {
        "description": "Search persistent decisions and lessons; returns authors and evidence references. "
                       "Set include_history to search past projects too.",
        "input_schema": {"type": "object", "properties": {
            "query": {"type": "string"}, "category": {"type": "string", "enum": list(CATEGORIES)},
            "include_history": {"type": "boolean"}}, "required": ["query"]},
    },
}
WORD = re.compile(r"[a-z0-9]{3,}")
STOP = {"the", "and", "for", "with", "that", "this", "from", "into", "your", "are", "was", "will", "should", "have",
        "has", "not", "but", "you", "all", "any", "can", "use", "its", "when", "what", "how", "why", "who"}


def words(text: str) -> set[str]:
    return {w for w in WORD.findall((text or "").lower()) if w not in STOP}


class Memory:
    def __init__(self, db: DB) -> None:
        self.db = db

    def remember(self, text: str, author: str, project_id: int | None, scope: str = "project",
                 category: str = "decision", source: str = "", evidence_files: list[str] | None = None,
                 *, evidence_root: Path | None = None) -> str:
        if scope not in ('project', 'company') or category not in CATEGORIES:
            raise ValueError('Use a supported memory scope and category.')
        text = " ".join(str(text).split())[:4000]
        if len(text) < 8:
            raise ValueError("Write the fact in a sentence or two.")
        pid = None if scope == "company" or not project_id else project_id
        if evidence_files and not pid:
            raise ValueError('File evidence requires project-scoped memory.')
        if evidence_files is not None and (not isinstance(evidence_files, list) or len(evidence_files) > 50
                                          or any(not isinstance(p, str) for p in evidence_files)):
            raise ValueError('Use at most 50 project-relative evidence paths.')
        hashes = {p: self._digest(pid, p, evidence_root) for p in evidence_files or []}
        same = self.db.one("SELECT id FROM memories WHERE lower(text)=lower(?) AND project_id IS ? AND category=?",
                           text, pid, category)
        if same:
            if hashes:
                self.db.run('UPDATE memories SET evidence_files=?, source=? WHERE id=?',
                            json.dumps(hashes, sort_keys=True), str(source)[:1000], same['id'])
            return "Already remembered."
        self.db.run("INSERT INTO memories (project_id, author, text, created_at, category, source, evidence_files) "
                    "VALUES (?,?,?,?,?,?,?)", pid, author, text, now(), category, str(source)[:1000],
                    json.dumps(hashes, sort_keys=True))
        self.db.log("memory", f"{author} remembered: {text[:120]}", project_id, actor=author)
        return "Remembered" + (" for the whole company." if pid is None else " for this project.")

    def _digest(self, project_id, path, evidence_root=None):
        project = self.db.one('SELECT workspace FROM projects WHERE id=?', project_id)
        if not project or Path(path).is_absolute() or '..' in Path(path).parts:
            raise ValueError('Evidence must be inside the project workspace.')
        root = Path(evidence_root or project['workspace']).resolve()
        target = (root/path).resolve()
        if not target.is_relative_to(root) or not target.is_file():
            raise ValueError('Evidence file is missing or outside the project.')
        if target.stat().st_size > 5_000_000:
            raise ValueError('Evidence file exceeds 5 MB.')
        return hashlib.sha256(target.read_bytes()).hexdigest()

    def _current(self, row):
        try:
            evidence = json.loads(row.get('evidence_files', '{}'))
            return all(self._digest(row['project_id'], p) == digest for p, digest in evidence.items())
        except (OSError, ValueError, AttributeError):
            return False

    def recall(self, project_id: int | None, about: str, limit: int = 8, *, category: str | None = None,
               include_history: bool = False) -> list[dict]:
        """Context injection retains recent conventions when an assignment has no matching keywords."""
        matched = self.search(project_id, about, limit, category=category, include_history=include_history)
        return matched or self.search(project_id, '', limit, category=category, include_history=include_history)

    def search(self, project_id: int | None, about: str, limit: int = 8, *, category: str | None = None,
               include_history: bool = False) -> list[dict]:
        """Indexed lexical retrieval across all retained memories, with explicit project scope."""
        if category is not None and category not in CATEGORIES:
            raise ValueError('Use a supported memory category.')
        limit = max(1, min(100, int(limit)))
        filters, args = [], []
        if not include_history:
            filters.append('(m.project_id IS NULL OR m.project_id=?)')
            args.append(project_id)
        if category:
            filters.append('m.category=?')
            args.append(category)
        where = (' AND ' + ' AND '.join(filters)) if filters else ''
        query = ' OR '.join('"' + w + '"' for w in sorted(words(about))[:50])
        if query:
            rows = self.db.all('SELECT m.* FROM memory_search JOIN memories m ON m.id=memory_search.rowid '
                               'WHERE memory_search MATCH ?' + where +
                               ' ORDER BY bm25(memory_search), m.id DESC LIMIT ?', query, *args, limit)
            if rows:
                return [r for r in rows if self._current(r)]
            return []
        return [r for r in self.db.all('SELECT m.* FROM memories m WHERE 1=1' + where +
                                      ' ORDER BY m.id DESC LIMIT ?', *args, limit) if self._current(r)]

    def list(self, project_id: int | None = None, limit: int = 50) -> list[dict]:
        if project_id:
            return self.db.all("SELECT * FROM memories WHERE project_id=? OR project_id IS NULL ORDER BY id DESC LIMIT ?",
                               project_id, limit)
        return self.db.all("SELECT * FROM memories ORDER BY id DESC LIMIT ?", limit)

    @staticmethod
    def as_text(memories: list[dict]) -> str:
        if not memories:
            return ""
        return ("What the team has learned (shared memory; follow it unless the CEO or CTO says otherwise):\n"
                + "\n".join(f"- [{m.get('category', 'decision')}] {m['text']} "
                            f"(by {m['author']}; source: {m.get('source') or 'not supplied'})" for m in memories))
