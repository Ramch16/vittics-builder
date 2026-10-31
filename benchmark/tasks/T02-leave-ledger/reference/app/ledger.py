class InsufficientBalance(Exception):
    pass


class InvalidTransition(Exception):
    pass


ALLOWED = {("pending", "approved"), ("pending", "cancelled"), ("approved", "cancelled")}


class Ledger:
    def __init__(self, balances):
        self._balances = dict(balances)
        self._requests = {}

    def available(self, employee):
        used = sum(r["days"] for r in self._requests.values()
                   if r["employee"] == employee and r["status"] in ("pending", "approved"))
        return self._balances[employee] - used

    def request(self, employee, days):
        if type(days) is not int or days <= 0:
            raise ValueError("days must be a positive integer")
        if days > self.available(employee):
            raise InsufficientBalance(employee)
        rid = len(self._requests) + 1
        self._requests[rid] = {"employee": employee, "days": days, "status": "pending"}
        return rid

    def status(self, request_id):
        return self._requests[request_id]["status"]

    def _move(self, request_id, target):
        req = self._requests[request_id]
        if (req["status"], target) not in ALLOWED:
            raise InvalidTransition(f"{req['status']} -> {target}")
        req["status"] = target

    def approve(self, request_id):
        self._move(request_id, "approved")

    def cancel(self, request_id):
        self._move(request_id, "cancelled")
