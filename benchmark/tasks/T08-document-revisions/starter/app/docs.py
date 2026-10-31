class StaleRevision(Exception):
    pass


class DocumentStore:
    def __init__(self, path):
        raise NotImplementedError
