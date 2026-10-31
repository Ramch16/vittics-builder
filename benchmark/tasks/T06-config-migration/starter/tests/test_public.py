import pytest
from app.migrate import UnsupportedVersion, migrate


def test_v1_to_v3():
    out = migrate({"version": 1, "db_host": "h", "db_port": 5432})
    assert out == {"version": 3, "database": {"host": "h", "port": 5432}, "timeouts": {"connect": 10}}


def test_unsupported():
    with pytest.raises(UnsupportedVersion):
        migrate({"version": 9})
