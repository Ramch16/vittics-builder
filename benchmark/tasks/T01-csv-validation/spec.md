# T01 CSV validation

Implement `app/csv_import.py`.

`import_rows(text: str, store: dict) -> dict` imports CSV text with the header `id,name,email`
(columns in any order; extra columns are ignored) into `store`, keyed by `id`, each value
`{"name": ..., "email": ...}` with surrounding whitespace stripped.

Requirements
- R1 Valid rows are added and the call returns `{"imported": <count>}`.
- R2 A missing required column in the header raises `ImportRejected`.
- R3 A row with an empty `id`, `name` or `email`, or an `email` without exactly one `@` with text on both
  sides, is an error.
- R4 A duplicate `id`, within the file or already in `store`, is an error.
- R5 If there is any error, raise `ImportRejected` whose `errors` attribute lists one message per bad row
  (`"line <n>: <reason>"`, header is line 1), and leave `store` unchanged (no partial writes).
- R6 An input with a header and no rows imports nothing and returns `{"imported": 0}`.
