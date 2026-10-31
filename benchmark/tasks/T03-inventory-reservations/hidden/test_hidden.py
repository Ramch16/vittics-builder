import pytest
from app.inventory import Inventory, OutOfStock


def test_failed_reserve_reserves_nothing():
    inv = Inventory()
    inv.add_stock("A", 3)
    inv.reserve("o1", "A", 2)
    with pytest.raises(OutOfStock):
        inv.reserve("o2", "A", 2)
    assert inv.available("A") == 1
    with pytest.raises(KeyError):
        inv.release("o2")


@pytest.mark.parametrize("qty", [0, -2, 1.0, True])
def test_bad_qty(qty):
    inv = Inventory()
    with pytest.raises(ValueError):
        inv.add_stock("A", qty)
    inv.add_stock("A", 5)
    with pytest.raises(ValueError):
        inv.reserve("o", "A", qty)


def test_multi_sku_order_and_accumulation():
    inv = Inventory()
    inv.add_stock("A", 5)
    inv.add_stock("B", 5)
    inv.reserve("o1", "A", 1)
    inv.reserve("o1", "A", 2)
    inv.reserve("o1", "B", 4)
    assert (inv.available("A"), inv.available("B")) == (2, 1)
    inv.release("o1")
    assert (inv.available("A"), inv.available("B")) == (5, 5)


def test_unknown_sku_and_reuse():
    inv = Inventory()
    assert inv.available("Z") == 0
    with pytest.raises(OutOfStock):
        inv.reserve("o1", "Z", 1)
    inv.add_stock("A", 2)
    inv.reserve("o1", "A", 2)
    inv.release("o1")
    inv.reserve("o1", "A", 1)
    assert inv.available("A") == 1
