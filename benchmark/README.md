# Benchmark package (pilot: implementation under shared requirements)

Decisions D8–D13 (`docs/research/decisions-2026-10-31.md`) fix the scope: both conditions get the same
frozen requirements, starter tree, public tests, builder role, model and attempt limit, and a separate oracle
judges the final tree.

| Path | What it is |
| --- | --- |
| `tasks/T0n-*/spec.md` | The frozen requirements (becomes `docs/PRD.md` in the run workspace) |
| `tasks/T0n-*/starter/` | Starter tree with stub code and the public tests (`tests/`) |
| `tasks/T0n-*/hidden/` | Hidden oracle tests. Never copied into a run workspace |
| `tasks/T0n-*/reference/` | Reference implementation, used only to validate the package |
| `oracle.py` | Independent evaluator: fresh temporary copy, frozen public tests and hidden tests, per-check results |
| `schedule.py`, `schedule-20261031.json` | Counterbalanced 48-slot schedule, seed 20261031 |
| `harness.py` | Runs slots under `multi_agent` (Vittics task loop) and `single_agent` (one builder) and writes schema-v2 records |

```
python -m benchmark.oracle validate                    # every starter fails, every reference passes
python -m benchmark.schedule --seed 20261031           # reproduces schedule-20261031.json
python -m benchmark.harness --schedule benchmark/schedule-20261031.json --out <folder>
```

## Tasks

| ID | Task | Checks (public + hidden) |
| --- | --- | --- |
| T01 | CSV validation without partial writes | 12 |
| T02 | Leave ledger state transitions | 12 |
| T03 | Inventory reservations, no oversell | 9 |
| T04 | Expense approval roles and final decisions | 10 |
| T05 | Daily totals across UTC offsets | 12 |
| T06 | Idempotent configuration migration | 11 |
| T07 | Dependency order, cycles and missing references | 8 |
| T08 | Document revisions with atomic persistence | 7 |

## Limits

- The harness accepts only the offline MockProvider. Its records are `data_kind: synthetic-mock` and show
  only that the harness, oracle and records work. Scripted mock agents do not attempt the tasks, so every run
  is rejected; that says nothing about either condition.
- Real-provider runs stay blocked until the model, per-run caps, aggregate budget and spending authorization
  (protocol P07, P10; decision D13) are set, and until the task adequacy and isolation reviews are done.
- Oracle isolation is a separate temporary folder in the same user account. It is not a separate machine
  or identity.
- Eight small synthetic tasks support narrow conclusions only.
