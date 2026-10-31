# Benchmark readiness report, 31 October 2026

**Bottom line:** the task package, independent oracle, schedule and both run conditions exist and work end to
end on the offline mock provider. **No real comparison has been run**, so there are no results about either
condition. A real pilot needs the inputs listed in §5.

## 1. What exists

| Part | State | Evidence |
| --- | --- | --- |
| 8 tasks (T01–T08) | Built: spec, failing starter, public tests, hidden tests, reference | `evidence/week3/task-package-validation.json`: all 8 valid; 81 checks; every starter passes 0, every reference passes all |
| Independent oracle | Built: fresh temp copy, frozen public tests restored, hidden tests added, JUnit per check | `test_oracle_uses_frozen_public_tests_not_the_agents_copy` |
| Schedule | Frozen: 48 slots, seed 20261031 | `benchmark/schedule-20261031.json`; `test_schedule_is_reproducible_and_counterbalanced` |
| `multi_agent` condition | Vittics task loop: builder, code review, QA, rework, minimum-review rule | `benchmark/harness.py` |
| `single_agent` condition | One builder, same tools, public-test feedback, same attempt limit (3) | `benchmark/harness.py` |
| Run records | Schema v2; validated and semantically checked | `evidence/week3/mock-pilot-20261031/validation.json`: 0 schema errors, 0 semantic issues |

## 2. Mock pilot (harness check, not a result)

Run on 31 October 2026 at harness commit `8f23390`, Linux, Python 3.13.18, MockProvider (scripted agents that
do not attempt the task). All 48 scheduled slots started and finished.

| | multi_agent | single_agent |
| --- | --- | --- |
| Runs | 24 | 24 |
| Accepted by the hidden oracle | 0 | 0 |
| Declared done (released) | 24 | 0 |
| False releases (released, oracle failed) | 24 | 0 |
| Builder rework attempts | 0 | 48 |
| Independent reviews per run | 2 | 0 |
| Summed wall time (s) | 12.4 | 36.9 |

How to read it: zero acceptance is expected, because mock agents write placeholder files. The useful signal
is that the pipeline works. The oracle rejected all 48 trees. The multi-agent loop declared every run done
because the scripted mock reviewers always approve; these runs count as false releases. The single-agent
loop stopped on failing public tests. A real model is needed before either number means anything.

Hashes: `records.jsonl` `2ce3750c35fb…200535a3`; `summary.json` `7760b25c6c5f…6ed3f52`;
`task-package-validation.json` `60bed7c8b795…94592`.

## 3. Fairness controls in place

- Same spec, starter tree, public tests, builder role, model and attempt limit in both conditions.
- Hidden tests and the reference never enter a run workspace. The oracle restores the original public
  tests, so editing `tests/` cannot help.
- Failed, blocked and rejected runs stay in the denominator. Unknown cost stays null, not zero.
- Conditions run back to back per task and repeat, in counterbalanced order.

## 4. Known confounds and limits

- The treatment is the whole Vittics configuration (reviews, QA, rework, prompts), not agent count.
- Eight small synthetic Python tasks, written for this study; generalization is narrow.
- The hidden tests have not been reviewed for adequacy by a person (Sanjana's packet). They may miss bugs.
- The oracle runs as the same user in a temporary folder, not on a separate machine or identity.
- Mock records exercise the harness only.

## 5. Needed before a real pilot

| Input | Owner per the plan | State |
| --- | --- | --- |
| Model, provider and per-run caps (tokens, seconds, cost) | Ramu, with all four | Unset (D13) |
| Aggregate budget and spending authorization (P10) | All four | None |
| Task adequacy review of T01–T08 hidden tests | Sanjana | Pending |
| Oracle and sandbox isolation check | Sai | Pending |
| Baseline design check (single_agent matches D11) | Nikhil | Pending |
| Runtime cap enforcement (hard stop on tokens and cost) | Engineering | **Not built.** Caps are recorded, not enforced. Required before paid runs |
| Real-provider path in the harness | Engineering | Deliberately refused until the items above are done |
