import pytest
from app.expenses import AlreadyDecided, Workflow

ROLES = {"eve": "employee", "max": "manager", "mia": "manager"}


def test_no_self_approval():
    wf = Workflow(ROLES)
    e = wf.submit("max", 500)
    with pytest.raises(PermissionError):
        wf.approve(e, "max")
    with pytest.raises(PermissionError):
        wf.reject(e, "max", "no")
    wf.approve(e, "mia")


def test_decisions_are_final():
    wf = Workflow(ROLES)
    e = wf.submit("eve", 500)
    wf.reject(e, "max", "missing receipt")
    for call in (lambda: wf.approve(e, "mia"), lambda: wf.reject(e, "mia", "x")):
        with pytest.raises(AlreadyDecided):
            call()
    got = wf.get(e)
    assert got["status"] == "rejected" and got["decided_by"] == "max" and got["reason"] == "missing receipt"


@pytest.mark.parametrize("amount", [0, -5, 10.5, True])
def test_bad_amount(amount):
    with pytest.raises(ValueError):
        Workflow(ROLES).submit("eve", amount)


def test_reason_required_and_unknowns():
    wf = Workflow(ROLES)
    e = wf.submit("eve", 1)
    with pytest.raises(ValueError):
        wf.reject(e, "max", "  ")
    with pytest.raises(KeyError):
        wf.submit("zed", 1)
    with pytest.raises(KeyError):
        wf.approve(e, "zed")
    assert wf.get(e)["status"] == "pending"


def test_get_returns_copy():
    wf = Workflow(ROLES)
    e = wf.submit("eve", 7)
    wf.get(e)["status"] = "approved"
    assert wf.get(e)["status"] == "pending"
