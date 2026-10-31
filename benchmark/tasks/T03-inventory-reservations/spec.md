# T03 Inventory reservations

Implement `app/inventory.py`: `Inventory()`.

- `add_stock(sku, qty)` adds on-hand stock.
- `reserve(order_id, sku, qty)` reserves stock for an order.
- `release(order_id)` releases every reservation of the order.
- `available(sku) -> int`: on hand minus reserved (0 for an unknown sku).

Requirements
- R1 `qty` must be a positive `int` (not bool) for `add_stock` and `reserve`; otherwise `ValueError`.
- R2 A reservation that would make `available` negative raises `OutOfStock` and reserves nothing.
- R3 An order may reserve several skus; reserving the same sku twice for one order adds to it.
- R4 `release` of an unknown order raises `KeyError`; after release the order id can be reused.
- R5 `reserve` of an unknown sku raises `OutOfStock`.
