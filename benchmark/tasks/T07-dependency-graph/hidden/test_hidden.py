import copy
import pytest
from app.graph import CycleError, MissingDependency, install_order


def test_alphabetical_tie_break():
    assert install_order({"c": [], "a": [], "b": ["c", "a"]}) == ["a", "c", "b"]


def test_diamond():
    deps = {"top": ["left", "right"], "left": ["base"], "right": ["base"], "base": []}
    assert install_order(deps) == ["base", "left", "right", "top"]


def test_missing_named():
    with pytest.raises(MissingDependency, match="ghost"):
        install_order({"a": ["ghost"]})


def test_cycle_members_exclude_bystanders():
    with pytest.raises(CycleError) as e:
        install_order({"x": ["y"], "y": ["z"], "z": ["x"], "w": ["x"], "v": []})
    assert e.value.members == ["x", "y", "z"]


def test_self_cycle_duplicates_and_no_mutation():
    with pytest.raises(CycleError) as e:
        install_order({"a": ["a"]})
    assert e.value.members == ["a"]
    deps = {"a": ["b", "b"], "b": []}
    before = copy.deepcopy(deps)
    assert install_order(deps) == ["b", "a"] and deps == before


def test_empty():
    assert install_order({}) == []
