class InsufficientBalance(Exception):
    pass


class InvalidTransition(Exception):
    pass


class Ledger:
    def __init__(self, balances):
        raise NotImplementedError
