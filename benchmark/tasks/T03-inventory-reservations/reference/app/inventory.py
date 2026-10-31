from collections import defaultdict


class OutOfStock(Exception):
    pass


def _qty(qty):
    if type(qty) is not int or qty <= 0:
        raise ValueError("qty must be a positive integer")
    return qty


class Inventory:
    def __init__(self):
        self._on_hand = defaultdict(int)
        self._orders = {}

    def add_stock(self, sku, qty):
        self._on_hand[sku] += _qty(qty)

    def available(self, sku):
        reserved = sum(o.get(sku, 0) for o in self._orders.values())
        return self._on_hand.get(sku, 0) - reserved

    def reserve(self, order_id, sku, qty):
        _qty(qty)
        if qty > self.available(sku):
            raise OutOfStock(sku)
        order = self._orders.setdefault(order_id, {})
        order[sku] = order.get(sku, 0) + qty

    def release(self, order_id):
        del self._orders[order_id]
