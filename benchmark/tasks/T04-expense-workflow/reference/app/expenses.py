class AlreadyDecided(Exception):
    pass


class Workflow:
    def __init__(self, roles):
        self._roles = dict(roles)
        self._items = {}

    def submit(self, user, amount_cents):
        self._roles[user]
        if type(amount_cents) is not int or amount_cents <= 0:
            raise ValueError("amount must be a positive integer")
        eid = len(self._items) + 1
        self._items[eid] = {"user": user, "amount_cents": amount_cents, "status": "pending",
                            "decided_by": None, "reason": None}
        return eid

    def _decide(self, expense_id, actor, status, reason=None):
        item = self._items[expense_id]
        if self._roles[actor] != "manager" or actor == item["user"]:
            raise PermissionError(actor)
        if item["status"] != "pending":
            raise AlreadyDecided(expense_id)
        item.update(status=status, decided_by=actor, reason=reason)

    def approve(self, expense_id, actor):
        self._decide(expense_id, actor, "approved")

    def reject(self, expense_id, actor, reason):
        if not str(reason or "").strip():
            raise ValueError("a reason is required")
        self._decide(expense_id, actor, "rejected", reason)

    def get(self, expense_id):
        return dict(self._items[expense_id])
