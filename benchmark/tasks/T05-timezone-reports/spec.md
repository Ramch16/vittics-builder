# T05 Timezone reports

Implement `app/reports.py`.

`daily_totals(events, offset_minutes) -> dict[str, int]` sums integer amounts per calendar day in the
fixed UTC offset `offset_minutes` (e.g. -300 for UTC-5). `events` is a list of `(timestamp, amount)` where
`timestamp` is an ISO 8601 string.

Requirements
- R1 Keys are `YYYY-MM-DD` in the target offset; days without events are absent.
- R2 A day runs from 00:00:00 inclusive to the next 00:00:00 exclusive, in the target offset.
- R3 A timestamp without an offset (naive) raises `ValueError`; so does an unparsable one.
- R4 `offset_minutes` outside -720..840 raises `ValueError`.
- R5 Amounts must be `int` (not bool); otherwise `ValueError`. Negative amounts are allowed (refunds).
- R6 The input list is not modified.
