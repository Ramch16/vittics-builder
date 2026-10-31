import pytest
from app.reports import daily_totals


def test_utc_grouping():
    events = [("2026-03-01T10:00:00+00:00", 5), ("2026-03-01T23:00:00+00:00", 2)]
    assert daily_totals(events, 0) == {"2026-03-01": 7}


def test_naive_rejected():
    with pytest.raises(ValueError):
        daily_totals([("2026-03-01T10:00:00", 5)], 0)
