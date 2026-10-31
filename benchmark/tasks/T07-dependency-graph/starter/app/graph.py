class MissingDependency(Exception):
    pass


class CycleError(Exception):
    def __init__(self, members):
        super().__init__(", ".join(members))
        self.members = list(members)


def install_order(deps):
    raise NotImplementedError
