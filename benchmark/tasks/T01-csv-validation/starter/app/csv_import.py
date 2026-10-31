class ImportRejected(Exception):
    def __init__(self, errors):
        super().__init__("; ".join(errors))
        self.errors = list(errors)


def import_rows(text, store):
    raise NotImplementedError
