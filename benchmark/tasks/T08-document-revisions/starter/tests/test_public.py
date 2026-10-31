import pytest
from app.docs import DocumentStore, StaleRevision


def test_create_update_get(tmp_path):
    s = DocumentStore(tmp_path / "docs.json")
    assert s.create("a", "v1") == 1
    assert s.update("a", "v2", 1) == 2
    assert s.get("a") == (2, "v2")


def test_stale_update(tmp_path):
    s = DocumentStore(tmp_path / "docs.json")
    s.create("a", "v1")
    s.update("a", "v2", 1)
    with pytest.raises(StaleRevision):
        s.update("a", "v3", 1)
