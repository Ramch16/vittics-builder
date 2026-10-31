# Matched single-agent baseline: interface and specification

# DRAFT — NOT APPROVED, NOT IMPLEMENTED

Prepared with AI assistance (Claude Code) on 2026-10-25 for **Nikhil** (architecture), who owns the design, and **Ramu** (benchmarks), who owns the measurement. Nothing here is a decision by either of them. Model choice, caps and task set stay open until the team approves the protocol in Weeks 3–4. No real-provider run is authorized by this document. It refines proposal P-08 and `benchmark-protocol-draft.md` §2.

## 1. Purpose

Compare the multi-agent pipeline (treatment) with one agent doing the same job (baseline). Both conditions get the same inputs, tools, model, limits and acceptance oracle. The intended difference is the treatment's planning, reviewer and audit stages; every other difference must be disclosed.

## 2. Shared inputs (frozen before any run, hashed in every run record)

| Input | Both conditions receive | Record field |
| --- | --- | --- |
| Brief | identical text | `hashes.task` |
| Requirements | identical PRD and requirements registry; schema-v2 `product.json` written in advance, not by the agents | `hashes.prompt` (prompt bundle) |
| Starter tree | identical git tree, restored fresh per run | `source.starter_tree_sha256` |
| Configuration | identical model ID, model settings, sandbox mode, engine and tool versions | `hashes.config`, `engine.*` |
| Hidden oracle | **neither** condition can read it; copied in only after the run ends | `hashes.oracle` |

## 3. Interface the baseline needs (proposed code shape, for Nikhil to accept or change)

| Element | Proposal |
| --- | --- |
| Entry point | `vittics-builder bench run --condition single_agent --task <id> --repeat <n>` (and `--condition multi_agent`), writing one run record per run |
| Single-agent role | One builder seat whose tools are the union of the treatment builders' tools (`read_file`, `write_file`, `replace_in_file`, `list_files`, `run_command`), same sandbox, no `delegate` |
| Instructions | Brief + requirements + "implement, test and finish"; no planner, reviewer or auditor prompts |
| Turn and time budget | Total per-run caps (§4) shared by the single agent; in the treatment, shared across **all** agents and retries |
| Product checks | Both may run the frozen `product.json` checks (`run_approved_checks`); these are working signals, not the oracle |
| Run record | Same schema (`run-record.schema.json` v2) and the same exporter for both conditions |
| Storage | One fresh company folder per run; nothing shared between runs |

## 4. Caps (values open)

| Cap | Rule | Value |
| --- | --- | --- |
| Total tokens | input + output across every agent, retry and engine in the run | **open (Ramu)** |
| Wall time | from run start to terminal status | **open (Ramu)** |
| Cost | estimated cost across the run; unknown cost counts as cap-unverifiable and is recorded | **open (Ramu)** |
| Over a cap | the run stops: `timeout` (time) or `failed` (tokens/cost), blocker = the cap; never `accepted` | `check_semantics` rule `caps-enforced` |

## 5. Human involvement (identical where it applies)

| Gate | Treatment | Baseline |
| --- | --- | --- |
| Requirements, design and plan approvals | pre-approved: frozen inputs, no live decision | not applicable |
| Safety stop (destructive command, secret access attempt, runaway cost) | same written checklist | same written checklist |
| Final release checklist | the same human checklist before the oracle runs | the same human checklist |
| Steering | not allowed except to unblock infrastructure; logged with minutes | same |

Treatment-only stages, disclosed as the treatment:
- per-task code review and QA (`review_mode` fixed per experiment);
- release audits;
- rework loops up to `max_rework`;
- escalation to the CTO checklist.

## 6. Outcomes (both conditions, from the hidden oracle)

| Outcome | Definition |
| --- | --- |
| Accepted | Terminal status `accepted` **and** the independent hidden oracle ran on the recorded evaluated tree with a nonempty, all-passing result (`benchmarks._accepted`) |
| Release-and-oracle success (overall) | runs released **and** accepted ÷ all runs started |
| Conditional release rate | runs released ÷ runs that reached a release decision (undefined if none did) |
| Cost per accepted run | total cost of **all** runs ÷ accepted runs; undefined if zero accepted or any cost unknown |

## 7. Unavoidable differences to disclose

- The baseline has no independent per-task review, so the treatment's extra review is the effect being measured, not a confound.
- The treatment spends tokens on coordination (plans, reviews). Equal total caps mean the baseline can spend all of them on building. This is deliberate and disclosed.
- Parallel work in the treatment can shorten wall time at equal token use, so report wall time and summed agent time separately.

## 8. Open decisions

| Decision | Owner |
| --- | --- |
| Accept or change the interface in §3 | Nikhil |
| Whether the baseline sees `product.json` checks or only the brief and PRD | Nikhil, Sanjana |
| Cap values, model ID and settings | Ramu, all four at protocol approval |
| Task set and oracle per task | Ramu, Sanjana |
| `review_mode` for the treatment | Nikhil, Ramu |
