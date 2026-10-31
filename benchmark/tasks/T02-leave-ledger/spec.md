# T02 Leave ledger

Implement `app/ledger.py`: `Ledger(balances: dict[str, int])`.

- `request(employee, days) -> int` creates a pending request and returns its id (1, 2, ...).
- `approve(request_id)`: pending -> approved.
- `cancel(request_id)`: pending or approved -> cancelled.
- `available(employee) -> int`: balance minus days in pending and approved requests.
- `status(request_id) -> str`: "pending", "approved" or "cancelled".

Requirements
- R1 `days` must be a positive `int` (not bool); otherwise `ValueError`.
- R2 Unknown employee: `KeyError`.
- R3 A request larger than `available` raises `InsufficientBalance` and creates nothing.
- R4 Any other transition (approve an approved/cancelled request, cancel a cancelled one) raises
  `InvalidTransition` and changes nothing. Unknown request id: `KeyError`.
- R5 Cancelling returns the days to `available`.
