import json
import os
import tempfile
from pathlib import Path


class StaleRevision(Exception):
    pass


class DocumentStore:
    def __init__(self, path):
        self.path = Path(path)
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
            except ValueError as exc:
                raise ValueError(f"corrupt store: {exc}") from exc
            self._docs = {k: [tuple(r) for r in v] for k, v in data.items()}
        else:
            self._docs = {}

    def _save(self):
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".docs-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self._docs, f)
            os.replace(tmp, self.path)
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    def create(self, doc_id, text):
        if doc_id in self._docs:
            raise ValueError(f"{doc_id} exists")
        self._docs[doc_id] = [(1, text)]
        self._save()
        return 1

    def get(self, doc_id):
        return self._docs[doc_id][-1]

    def history(self, doc_id):
        return list(self._docs[doc_id])

    def update(self, doc_id, text, base_revision):
        revisions = self._docs[doc_id]
        latest = revisions[-1][0]
        if base_revision != latest:
            raise StaleRevision(f"{doc_id}: base {base_revision}, latest {latest}")
        revisions.append((latest + 1, text))
        self._save()
        return latest + 1
