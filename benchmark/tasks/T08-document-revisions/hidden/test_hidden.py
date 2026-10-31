import os
import pytest
from app.docs import DocumentStore, StaleRevision


def test_reload_keeps_history(tmp_path):
    path = tmp_path / "docs.json"
    s = DocumentStore(path)
    s.create("a", "one")
    s.update("a", "two", 1)
    again = DocumentStore(path)
    assert again.history("a") == [(1, "one"), (2, "two")] and again.get("a") == (2, "two")


def test_stale_changes_nothing_on_disk(tmp_path):
    path = tmp_path / "docs.json"
    s = DocumentStore(path)
    s.create("a", "one")
    s.update("a", "two", 1)
    before = path.read_bytes()
    with pytest.raises(StaleRevision):
        s.update("a", "lost", 1)
    assert path.read_bytes() == before and DocumentStore(path).get("a") == (2, "two")


def test_duplicates_and_unknowns(tmp_path):
    s = DocumentStore(tmp_path / "d.json")
    s.create("a", "x")
    with pytest.raises(ValueError):
        s.create("a", "y")
    for call in (lambda: s.get("zz"), lambda: s.history("zz"), lambda: s.update("zz", "t", 1)):
        with pytest.raises(KeyError):
            call()


def test_missing_and_corrupt_files(tmp_path):
    missing = tmp_path / "none.json"
    with pytest.raises(KeyError):
        DocumentStore(missing).get("a")
    assert not missing.exists()
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    with pytest.raises(ValueError):
        DocumentStore(bad)


def test_atomic_replace_used(tmp_path, monkeypatch):
    calls = []
    real = os.replace
    monkeypatch.setattr(os, "replace", lambda a, b: (calls.append((str(a), str(b))), real(a, b))[1])
    path = tmp_path / "docs.json"
    DocumentStore(path).create("a", "x")
    assert calls and calls[-1][1] == str(path) and os.path.dirname(calls[-1][0]) == str(tmp_path)
