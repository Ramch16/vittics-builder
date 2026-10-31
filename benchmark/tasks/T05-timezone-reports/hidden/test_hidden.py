import pytest
from app.reports import daily_totals


def test_offset_moves_day():
    events = [("2026-03-02T03:00:00+00:00", 4)]
    assert daily_totals(events, -300) == {"2026-03-01": 4}
    assert daily_totals(events, 0) == {"2026-03-02": 4}


def test_boundaries():
    events = [("2026-03-01T05:00:00+00:00", 1),       # 00:00 at UTC-5: belongs to Mar 1
              ("2026-03-01T04:59:59+00:00", 10)]      # 23:59:59 Feb 28 at UTC-5
    assert daily_totals(events, -300) == {"2026-03-01": 1, "2026-02-28": 10}


def test_input_offsets_are_respected_and_refunds():
    events = [("2026-03-01T22:30:00-02:00", 3), ("2026-03-02T00:10:00+00:00", -1)]
    assert daily_totals(events, 0) == {"2026-03-02": 2}


@pytest.mark.parametrize("offset", [-721, 841])
def test_bad_offset(offset):
    with pytest.raises(ValueError):
        daily_totals([], offset)


@pytest.mark.parametrize("amount", [1.5, True, "3"])
def test_bad_amount(amount):
    with pytest.raises(ValueError):
        daily_totals([("2026-03-01T10:00:00+00:00", amount)], 0)


def test_garbage_timestamp_and_input_unchanged():
    with pytest.raises(ValueError):
        daily_totals([("yesterday", 1)], 0)
    events = [("2026-03-01T10:00:00+00:00", 1)]
    copy = list(events)
    daily_totals(events, 60)
    assert events == copy


def test_half_hour_offset():
    assert daily_totals([("2026-03-01T18:45:00+00:00", 1)], 330) == {"2026-03-02": 1}
