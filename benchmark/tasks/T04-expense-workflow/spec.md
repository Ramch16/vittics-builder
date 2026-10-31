# T04 Expense workflow

Implement `app/expenses.py`: `Workflow(roles: dict[str, str])`, roles are "employee" or "manager".

- `submit(user, amount_cents) -> int`: a pending expense id (1, 2, ...).
- `approve(expense_id, actor)` and `reject(expense_id, actor, reason)`.
- `get(expense_id) -> dict` with keys `user`, `amount_cents`, `status` ("pending", "approved",
  "rejected"), `decided_by` (None until decided) and `reason` (None unless rejected).

Requirements
- R1 `amount_cents` must be a positive `int` (not bool); otherwise `ValueError`. Unknown users: `KeyError`.
- R2 Only a manager may approve or reject (`PermissionError`), and never their own expense (`PermissionError`).
- R3 A decision is final: deciding a decided expense raises `AlreadyDecided` and changes nothing.
- R4 `reject` needs a non-empty reason (`ValueError`).
- R5 `get` returns a copy; changing it does not change the stored expense.
