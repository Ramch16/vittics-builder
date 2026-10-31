# Benchmark protocol: multi-agent vs matched single-agent

# DRAFT — NOT APPROVED FOR EXPERIMENTS

Status: skeleton prepared with AI assistance (Claude Code) for **Ramu** to draft from. No paid run is
authorized by this file. Final protocol and any paid-run approval need all four human owners, after the
literature review planned for Weeks 3–4. The roadmap's pilot budget is a provisional figure, not an
authorization to spend or a record of spending.

This is a different study from the v0.24-vs-v0.25 regression protocol in `docs/capability-audit.md`, which
compares two versions of the same multi-agent system.

## 1. Question

Does a human-governed multi-agent workflow (Vittics Builder's pipeline) improve acceptance-test completion
and release reliability over a matched single-agent baseline, at acceptable cost? The pilot is exploratory.
Its results are not evidence of improvement, savings or reliability in general.

## 2. Conditions

| | Multi-agent (treatment) | Single-agent (baseline) |
| --- | --- | --- |
| Agents | Pipeline roles per `org.yaml` (PM, architect, builders, reviewers, QA, auditors) | One builder agent |
| Human gates | Same gates, decided by a fixed rule (see §6) | Same gates where applicable, same rule |
| Model and provider | Fixed, identical model ID and settings for every role | Same model ID and settings |
| Tools | Workspace tools; same sandbox mode | Same tools, same sandbox mode |
| Acceptance oracle | Independent, frozen, outside the workspace (§4) | Same oracle |
| Caps | Same token, time and cost caps per task | Same caps |

**Open (Ramu, Nikhil):** the single-agent condition does not exist in code yet (audit proposal P-08). Its
definition must be frozen before any result is seen. Unavoidable differences (e.g. no independent review in
the baseline) are disclosed, not equalized away.

## 3. Task set

- **6–10 fixed synthetic tasks**, each with a written selection rationale and a difficulty label (small /
  medium / multi-module) chosen before any run. No real customer data; no private immigration material.
- Each task has a frozen **starter tree** (hash recorded), **prompt**, **requirements** and **oracle**
  (hashes recorded in every run record).
- **Open (Ramu, Sanjana):** the task list itself.

## 4. Acceptance oracle

- The oracle is a test suite kept **outside** the agents' workspace and copied in only after the run ends,
  so neither condition can see or edit it. Agent-written tests and `product.json` checks are recorded but are
  not the oracle.
- A run is **accepted** only if the oracle passes on the final tree. Tracker "done" status is not acceptance.
- The evaluator is never tuned after results are seen. Any change to it starts a new experiment ID.

## 5. Repeats, order and environment

- Three repeats per task × condition where affordable; fewer is recorded as a deviation.
- Run order randomized by a recorded seed, alternating conditions per task (counterbalancing). The seed and
  resulting order are written before the first run.
- One machine profile per experiment, described by an evidence capture (`scripts/capture_evidence.py`);
  every record points at it through `environment_ref`. Fixed concurrency (`pipeline.max_parallel`).

## 6. Rules fixed in advance

| Item | Rule (draft) |
| --- | --- |
| Human gates | Approve when the gate's evidence meets a written checklist; reject otherwise. Each decision is logged as an intervention with minutes. |
| Steering | Not allowed during runs, except to unblock infrastructure; any steer is an intervention. |
| Retries | `builder_rework` = a review sent work back; `reviewer_retry` = a review re-run without new build; `infrastructure_retry` = provider or tool failure re-run. Counted separately. |
| Provider unavailable | Wait up to a fixed time, then terminal status `provider_unavailable`; never silently re-run as a new repeat. |
| Caps | Hit cap → terminal status `timeout` (time) or `failed` (tokens/cost), with the cap recorded as the blocker. |
| Terminal statuses | `accepted`, `rejected`, `failed`, `blocked`, `timeout`, `provider_unavailable`, `incomplete` (schema enum). |

## 7. What is recorded

Every run produces one record valid against `run-record.schema.json`. That file is the contract. Its main rules:

- **Unknown is `null`, never `0`.** That applies to tokens, cost, versions and waits.
- `data_kind` is `observed` for real-provider runs, and `synthetic` or `synthetic-mock` otherwise. Synthetic records never go in an actual-results folder.
- Cost carries a `basis` (`billed`, `estimated`, `subscription_unpriced`, `unknown`), plus currency and price-source date. A subscription engine's recorded `$0` is `subscription_unpriced` with `amount: null`. It is not an economic cost of zero.
- Usage keeps input, output, cache-read and cache-write tokens separately where the provider reports them.
- Failed, timed-out and incomplete runs are kept, along with their cost.
- Artifact and log hashes link each record to its raw files.
- **Schema version 2 (Week 2 draft)** adds `acceptance.oracle` (`kind`, `evaluated_tree`, `run_ref`) and per-run `caps`.
- **Consistency rules beyond the schema** are enforced by `benchmarks.check_semantics`:
    - unique run IDs;
    - end not before start;
    - only `incomplete` runs lack an end;
    - `accepted` requires the independent hidden oracle, an evaluated tree and a nonempty all-passing result;
    - `all_passed` must agree with the checks;
    - an oracle result carries tree and run references;
    - unknown or subscription-unpriced cost has a null amount, while billed or estimated cost has an amount and currency;
    - a run over any cap cannot end `accepted` or `rejected`.

## 8. Metrics

| Metric | Definition |
| --- | --- |
| Acceptance rate | accepted runs / all runs, per task × condition |
| Release-and-oracle success (overall) | runs both `released` and accepted by the oracle / **all** runs started |
| Conditional release rate | runs `released` / runs that reached a release decision (undefined if none reached it). Reported beside the overall rate, never instead of it |
| Wall time | first start to last end of the run |
| Active union time | union of agent intervals, overlaps counted once (`benchmarks.summarize`) |
| Summed agent time | sum of agent intervals |
| Waits | human, provider-unavailable, infrastructure, unclassified; never subtracted from wall time silently |
| Total cost | sum over **all** runs, including failed ones; `null` if any run's cost is unknown |
| Cost per accepted run | total cost / accepted runs; **undefined (`null`) when accepted runs = 0** or total cost is unknown |
| Human minutes | sum of intervention minutes; `null` if any is unknown |

## 9. Analysis (pre-registered draft)

- Summaries are **task-paired**: for each task, the treatment-minus-baseline difference in acceptance rate over its repeats; then the median and range of those per-task differences, with sample counts.
- Repeats are clustered by task, so the unit of analysis is the task, not the run. With 6–10 tasks, report descriptive statistics and per-task values. Any interval estimate must resample tasks, not runs.
- No significance claim from the pilot.
- `benchmarks.summarize_records` implements these summaries. The synthetic dry runs in `evidence/week1/` (schema v1) and `evidence/week2/` (schema v2) exercise them: unknown-cost propagation, a failed run, an incomplete run, and a condition with zero accepted runs. Week 2 also adds 10 deliberately inconsistent records, each caught by its rule.
- The matched single-agent condition is specified in `single-agent-baseline-spec.md` (draft, not implemented).

## 10. Approvals

| Owner | Approves | Status |
| --- | --- | --- |
| Ramu | Protocol draft, fairness, raw-data handling | **Not given** |
| Nikhil | Single-agent condition design | **Not given** |
| Sanjana | Task set and requirements adequacy | **Not given** |
| Sai | Security of the harness and fixtures | **Not given** |
| All four | Paid-run authorization and budget | **Not given** |
