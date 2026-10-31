import csv
import io

REQUIRED = ("id", "name", "email")


class ImportRejected(Exception):
    def __init__(self, errors):
        super().__init__("; ".join(errors))
        self.errors = list(errors)


def _valid_email(value):
    local, at, domain = value.partition("@")
    return at == "@" and local and domain and "@" not in domain


def import_rows(text, store):
    reader = csv.DictReader(io.StringIO(text))
    header = [h.strip() for h in (reader.fieldnames or [])]
    missing = [c for c in REQUIRED if c not in header]
    if missing:
        raise ImportRejected([f"line 1: missing column {c}" for c in missing])
    reader.fieldnames = header
    staged, errors, seen = {}, [], set()
    for line, row in enumerate(reader, start=2):
        values = {c: (row.get(c) or "").strip() for c in REQUIRED}
        empty = [c for c in REQUIRED if not values[c]]
        if empty:
            errors.append(f"line {line}: empty {empty[0]}")
        elif not _valid_email(values["email"]):
            errors.append(f"line {line}: invalid email")
        elif values["id"] in seen or values["id"] in store:
            errors.append(f"line {line}: duplicate id {values['id']}")
        else:
            staged[values["id"]] = {"name": values["name"], "email": values["email"]}
        if values["id"]:
            seen.add(values["id"])
    if errors:
        raise ImportRejected(errors)
    store.update(staged)
    return {"imported": len(staged)}
