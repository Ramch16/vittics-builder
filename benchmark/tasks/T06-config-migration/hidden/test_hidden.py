import copy
import pytest
from app.migrate import UnsupportedVersion, migrate


def test_v2_with_connect_timeout_and_extra_keys():
    cfg = {"version": 2, "database": {"host": "h", "port": 1}, "connect_timeout": 3, "name": "svc"}
    assert migrate(cfg) == {"version": 3, "database": {"host": "h", "port": 1}, "timeouts": {"connect": 3},
                            "name": "svc"}


def test_idempotent():
    out = migrate({"version": 1, "db_host": "h", "db_port": 1})
    assert migrate(out) == out and migrate(out) is not out


def test_input_not_mutated_including_nested():
    cfg = {"version": 2, "database": {"host": "h", "port": 1}}
    before = copy.deepcopy(cfg)
    out = migrate(cfg)
    out["database"]["host"] = "changed"
    assert cfg == before


@pytest.mark.parametrize("cfg", [{}, {"version": True}, {"version": 0}, {"version": 4}, {"version": "1"}])
def test_unsupported_versions(cfg):
    with pytest.raises(UnsupportedVersion):
        migrate(cfg)


def test_v1_missing_keys_and_no_mutation_on_failure():
    cfg = {"version": 1, "db_host": "h"}
    with pytest.raises(ValueError):
        migrate(cfg)
    assert cfg == {"version": 1, "db_host": "h"}
