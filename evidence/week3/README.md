# Week 3 evidence

| Path | What | How it was produced |
| --- | --- | --- |
| `task-package-validation.json` | Every task's hashes and whether the starter fails and the reference passes | `python -m benchmark.oracle validate` at commit `8f23390` |
| `mock-pilot-20261031/records.jsonl` | 48 schema-v2 run records, `data_kind: synthetic-mock` | `python -m benchmark.harness --schedule benchmark/schedule-20261031.json --out evidence/week3/mock-pilot-20261031` at commit `8f23390` |
| `mock-pilot-20261031/oracle/` | Oracle output for each run | the same command |
| `mock-pilot-20261031/validation.json` | Schema and semantic checks (all empty) | the same command |
| `mock-pilot-20261031/summary.json` | `benchmarks.summarize_records` output | the same command |

Environment: Linux x86_64, Python 3.13.18, bubblewrap 0.9.0, MockProvider (no model, no network, no cost).
These records test the harness. They are not results for either condition.
