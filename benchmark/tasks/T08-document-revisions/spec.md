# T08 Document revision API

Implement `app/docs.py`: `DocumentStore(path)` keeps documents in a JSON file at `path`.

- `create(doc_id, text) -> int` creates revision 1.
- `update(doc_id, text, base_revision) -> int` creates the next revision.
- `get(doc_id) -> (revision, text)` returns the latest revision.
- `history(doc_id) -> list[(revision, text)]`, oldest first.

Requirements
- R1 `update` with a `base_revision` that is not the latest raises `StaleRevision` and changes nothing.
- R2 `create` of an existing id raises `ValueError`; unknown ids raise `KeyError`.
- R3 Every change is saved before the call returns: a new `DocumentStore(path)` sees it, with full history.
- R4 Saving is atomic: write to a temporary file in the same folder, then replace (never a partial file).
- R5 A missing file means an empty store; a corrupt file raises `ValueError` on load.
