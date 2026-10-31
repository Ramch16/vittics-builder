import pytest
from app.ledger import InsufficientBalance, InvalidTransition, Ledger


def test_pending_and_approved_both_count():
    l = Ledger({"ana": 10})
    a = l.request("ana", 4)
    l.approve(a)
    l.request("ana", 5)
    assert l.available("ana") == 1
    with pytest.raises(InsufficientBalance):
        l.request("ana", 2)


def test_cancel_restores():
    l = Ledger({"ana": 5})
    a = l.request("ana", 5)
    l.approve(a)
    l.cancel(a)
    assert l.available("ana") == 5 and l.status(a) == "cancelled"


@pytest.mark.parametrize("days", [0, -1, 1.5, True, "2"])
def test_bad_days(days):
    with pytest.raises(ValueError):
        Ledger({"ana": 5}).request("ana", days)


def test_invalid_transitions_change_nothing():
    l = Ledger({"ana": 5})
    a = l.request("ana", 2)
    l.cancel(a)
    for op in (l.approve, l.cancel):
        with pytest.raises(InvalidTransition):
            op(a)
    assert l.status(a) == "cancelled" and l.available("ana") == 5
    b = l.request("ana", 1)
    l.approve(b)
    with pytest.raises(InvalidTransition):
        l.approve(b)


def test_unknowns():
    l = Ledger({"ana": 5})
    with pytest.raises(KeyError):
        l.request("bob", 1)
    with pytest.raises(KeyError):
        l.approve(99)


def test_failed_request_creates_nothing():
    l = Ledger({"ana": 1})
    with pytest.raises(InsufficientBalance):
        l.request("ana", 2)
    assert l.request("ana", 1) == 1
