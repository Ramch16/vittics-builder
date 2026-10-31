import pytest
from app.expenses import Workflow


def test_manager_approves():
    wf = Workflow({"eve": "employee", "max": "manager"})
    e = wf.submit("eve", 1200)
    wf.approve(e, "max")
    assert wf.get(e)["status"] == "approved" and wf.get(e)["decided_by"] == "max"


def test_employee_cannot_approve():
    wf = Workflow({"eve": "employee", "bob": "employee"})
    e = wf.submit("eve", 1200)
    with pytest.raises(PermissionError):
        wf.approve(e, "bob")
