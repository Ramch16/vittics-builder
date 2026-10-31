import pytest
from app.graph import CycleError, install_order


def test_simple_chain():
    assert install_order({"app": ["lib"], "lib": []}) == ["lib", "app"]


def test_cycle():
    with pytest.raises(CycleError):
        install_order({"a": ["b"], "b": ["a"]})
