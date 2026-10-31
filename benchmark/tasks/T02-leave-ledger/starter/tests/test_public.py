import pytest
from app.ledger import InsufficientBalance, Ledger


def test_request_reduces_available():
    l = Ledger({"ana": 10})
    rid = l.request("ana", 3)
    assert l.status(rid) == "pending" and l.available("ana") == 7


def test_cannot_overdraw():
    with pytest.raises(InsufficientBalance):
        Ledger({"ana": 2}).request("ana", 3)
