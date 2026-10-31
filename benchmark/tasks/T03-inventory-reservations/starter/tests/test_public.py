import pytest
from app.inventory import Inventory, OutOfStock


def test_reserve_and_release():
    inv = Inventory()
    inv.add_stock("A", 5)
    inv.reserve("o1", "A", 3)
    assert inv.available("A") == 2
    inv.release("o1")
    assert inv.available("A") == 5


def test_no_oversell():
    inv = Inventory()
    inv.add_stock("A", 1)
    with pytest.raises(OutOfStock):
        inv.reserve("o1", "A", 2)
