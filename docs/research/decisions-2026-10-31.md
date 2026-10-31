# Decision record, 31 October 2026

**Decided by:** Ram Thondapu (project lead), in writing on 31 October 2026.
**Scope:** the open policy and protocol choices listed in `week2-evidence-readiness.md` §5 and the Week 3
protocol register (P01–P10).

The operating plan names other owners for several of these areas: Nikhil for architecture and review policy,
Sanjana for requirements and task adequacy, Sai for security and isolation, and Ramu for the benchmark
protocol. Those owners have **not** reviewed or approved these decisions; their reviews are tracked as
pending in the contributor task packets (`docs/research/task-packets/`). An owner may confirm, amend or
replace a decision; any change gets a new dated entry here.

## Review and safety policies

| ID | Question | Decision | Implemented in | Status |
| --- | --- | --- | --- | --- |
| D1 | A ticket with no available checker (A-01, from W1-F2/W1-S2) | The ticket is never marked done. It stays open, and the build stops with a resumable error naming the missing reviewer | `pipeline.py` `_run_task`; `test_no_task_is_done_without_an_independent_review` | Implemented; Nikhil's review pending |
| D2 | Minimum independent reviews per ticket | 1 in light and standard mode, 2 in thorough mode | `Pipeline.min_reviews` | Implemented; Nikhil's review pending |
| D3 | A contract without a requirements registry (W1-F1) | Still eligible for release, but the release approval states "Coverage: legacy-unmapped" | `pipeline.py` release approval; `test_release_reviewer_is_told_when_requirements_are_unmapped` | Implemented; Nikhil's review pending |
| D4 | Shell access for reviewer roles | Reviewer roles get no `run_command` (no Bash on Claude Code); they can still ask for approved checks, which run on the host. QA keeps its shell | `agent.py`; `test_reviewer_roles_get_no_shell` | Implemented; Nikhil's review pending |
| D5 | The five unverified CLI adapters (SEC-08) | Refused for read-only roles in a project workspace until each adapter's read-only mode is verified; builders unchanged | `engines.run_cli`; `test_unverified_adapters_refuse_read_only_roles_in_a_workspace` | Implemented; Nikhil and Sai review pending |
| D6 | README claim that every task gets a security review (W1-F3) | Correct the README: security review runs on every task only in thorough mode | `README.md` | Implemented |
| D7 | Secrets reachable from agent commands (SEC-01, SEC-03) | Keep company data out of reach of agent commands and give those commands an allowlisted environment. As built: bubblewrap (Linux) or sandbox-exec (macOS) hides `<company>/.vittics`, and values carrying URL passwords are dropped | `tools.py`; `test_security_boundaries.py` | Implemented where a sandbox backend works; open on Windows and on Linux without bubblewrap; Sai's review pending |

## Benchmark protocol (offline and mock only until a budget is approved)

| ID | Question | Decision | Implemented in | Status |
| --- | --- | --- | --- | --- |
| D8 | Pilot scope (P01) | Implementation under shared, frozen requirements; brief-to-release is a later, separate study | `benchmark/harness.py` | Implemented for mock runs |
| D9 | Tasks (P03) | All eight candidates, T01–T08 | `benchmark/tasks/` | Implemented; Sanjana's adequacy review pending |
| D10 | Repeats and order | 3 repeats per task per condition, 48 slots, seed 20261031, counterbalanced | `benchmark/schedule-20261031.json` | Implemented; Ramu's review pending |
| D11 | Baseline (P04) | One persistent builder with the same tools, the same public checks as feedback and the same attempt limit | `benchmark/harness.py` (`single_agent`) | Implemented for mock runs; Nikhil's review pending |
| D12 | Primary metric (P08) | Hidden-oracle acceptance per started run, with failures and timeouts in the denominator | `benchmark/oracle.py`; `benchmarks.summarize_records` | Implemented; Ramu's review pending |
| D13 | Model for the real study (P07) | Left unset. The model and caps are chosen when a budget is approved | `EXPERIMENT-FREEZE-DRAFT.json` (still null) | Open by decision |

## Identity

| ID | Question | Answer |
| --- | --- | --- |
| D14 | Who authored the commits recorded as "thondapu lakshman" | Sai Lakshman Naidu Thondapu, as stated by Ram Thondapu. Whether this is the same person as the team's security owner, Sai, has been asked but not yet confirmed. |

## Not decided here

- Spending authorization and the aggregate budget (P10): **none given**. The harness refuses real providers.
- Hosted-image isolation (SEC-06), encryption at rest (SEC-12) and approval wording for vault values seen by
  product code (SEC-07).
