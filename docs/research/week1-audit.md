# Week 1 audit: architecture and requirement evidence

Status: **draft, prepared with AI assistance (Claude Code), not yet reviewed by the human owners.**
Captured 2026-10-25. Every statement below is either an observed fact with a source line, or marked
*inference*, *unverified* or *open*. Line numbers refer to commit `f01a108` unless a different commit is named.

## 1. Baseline identity

| Item | Value |
| --- | --- |
| Audited commit (Week 1 read-only audit) | `89694d5142ddf2fe5055643c306b683c67665026` (v0.26.0, tree recorded in the capture manifest) |
| Current `main` at capture | `f01a108efddd741c9a4f1f6b62bb84215ef333aa`, tree `ed1c7e1d1b45aec03fc247415e72b32cc0239cd5` |
| Difference | PRs #8, #9, #10 merged on 2026-10-25: 12 files, +302/−23 lines |
| Work branch | `research/week1-evidence` (local only; not pushed under this handoff) |

What changed since the audit, and whether it affects this document:

- **#8** adds `tests/test_security_boundaries.py` (strict-xfail tests for SEC-01, SEC-03, SEC-05). Tests only.
- **#9** changes `engines.run_cli`: CLI engines get a scrubbed environment plus per-engine `env_keep` (`engines.py`, `engine_env`). Affects the threat model, not the release-evidence path.
- **#10** adds `projects.autopilot_roles`; autopilot decides only the gates of whoever chose the level (`autopilot.py`, `server.py`). Affects the approval trace below.

Historical CI run `38784041044` on `89694d5` (2026-10-15) has conclusion `success` for all five jobs, confirmed via the GitHub REST API. Its per-job test counts could not be re-read: job-log downloads redirect to a blob host this environment cannot reach (**blocked**). Fresh counts come from the captures under `evidence/week1/`.

## 2. Component map

| Component | Source | Role in the evidence path |
| --- | --- | --- |
| `Company` | `company.py:55` | Builds settings, DB, org, runtime, pipeline and add-ons for one company folder |
| `AgentRuntime` | `agent.py:39`, `run()` `:88` | Runs one agent on the API, a CLI engine or a worker node; records `runs`, `run_events`, `usage` |
| `Pipeline` | `pipeline.py` | State machine; `advance()` `:272`; human gates via `_approval()` `:125` and `decide()` `:1359` |
| `DB` | `db.py` | SQLite schema and in-place migrations (`_migrate` `:354`) |
| `Workspace` | `tools.py:206` | Confined file tools, command runner (local regex deny list or Docker), git bookkeeping |
| Validation | `validation.py` | Contract parsing, requirement coverage, check execution, fingerprints |
| Engines | `engines.py` | CLI adapters and their permission flags |
| Export | `delivery.py:10` `export_product` | Zips the signed-off `release` tag |

## 3. One synthetic brief, end to end

`scripts/trace_synthetic_brief.py` runs the brief *"A small Python library with a core module and a supporting module, each with unit tests"* on `MockProvider` (`data_kind: synthetic-mock`). It approves each gate in the script, standing in for the CEO and CTO. The raw output is `synthetic-trace.json` in the result capture; the gate sequence was the same in both captures:

| # | Gate (kind) | Required role | Stage before → after |
| --- | --- | --- | --- |
| 1 | `prd` | CEO | `prd_approval` → `architecture_approval` |
| 2 | `architecture` (pins `product.json`) | CTO | `architecture_approval` → `release_approval` |
| 3 | `release` | CTO | `release_approval` → `signoff` |
| 4 | `signoff` | CEO | `signoff` → `done` |

Observed on the mock run:

- **Two ledger rows** in `verification_runs`. Both report `passed: true`, `release_eligible: true` and `coverage: "legacy-unmapped"`, with no requirements registry.
- The release approval payload names the second ledger row and a `verified_head`.
- After sign-off the `release` tag's tree equals the verified tree (`release_tree_matches_verified_tree: true`).
- The exported zip contains `docs/VERIFICATION.json`.

Walk-through with sources:

1. **Requirements.** `_prd` (`pipeline.py:558`) has the PM write `docs/PRD.md`, then raises a `prd` gate for the CEO (`:613`).
2. **Product contract and tasks.** `_architecture` (`:621`) has the architect write `docs/ARCHITECTURE.md`, `product.json` and a plan.
   - `validate_plan` (`validation.py:77`) rejects empty plans, duplicate or invalid keys, unstaffed roles, missing descriptions, unknown dependencies and cycles.
   - The CTO's `architecture` approval stores the contract text in its payload (`:685`); `_approved_contract` (`:887`) later reads the newest approved `architecture` or `contract` payload.
3. **Build and per-task review.** `_run_task` (`:1146`) builds each task.
   - If `pipeline.review_checks` is on and a contract exists, it runs the contract checks without recording (`_host_checks(..., record=False)`, `:1221-1227`). The results go into the reviewer prompt as context, not as release evidence.
   - Reviewers come from `_checkers` (`:1091`): `thorough` = every staffed reviewer and QA role; `standard` (default) = one reviewer (code reviewer first) + one QA; `light` (and every *small* project) = one.
4. **Release checks.** `_build` (`:707`) runs release QA, audits and host checks.
   - `_contract_unchanged` (`:893`) compares the current `product.json` with the approved text through `same_contract` (`validation.py:163`). Only `schema_version`, `name`, `checks`, `serve` and `requirements` are compared; any difference raises a CTO `contract` gate with a diff.
   - `_host_checks` (`:907`) refuses to run anything unless the contract matches the approved one (`:911-912`). It then records `source_fingerprint` and HEAD before and after `verify_product`, fails the report if either moved (`:921-926`), and writes a `verification_runs` row (`:927`).
5. **Verification.** `verify_product` (`validation.py:177`):
   - Runs every check, or a subset `ids`, through `Workspace.run_command`, with the project's vault keys and `max_seconds = check_timeout`.
   - Requires non-empty `README.md` and `docs/OPERATIONS.md`, and redacts vault values in output.
   - Computes `requirements` from the check outcomes, ignoring any agent-written `status` (`requirement_results`, `:156-160`).
   - Sets `release_eligible = passed and ids is None and every requirement eligible`.
6. **Release gate.** The CTO `release` approval carries `verified_head` and `ledger_id` (`pipeline.py:815-817`).
   - `decide()` refuses to approve `release`, `signoff` or `task_review` if the tree is dirty or HEAD differs from `verified_head` (`:1390-1393`).
   - For `release` and `signoff` it also requires the ledger row to be `release_eligible` with a matching `source_sha256` and `verifier` identity (`:1394-1399`).
   - `release_blocked` can never be approved (`:1388`).
7. **Sign-off and export.** On CEO sign-off the pipeline makes an `--allow-empty` commit and tags `release` and `vN` (`:1527-1536`). `export_product` (`delivery.py:10-34`):
   - requires stage `done`/`live`, a clean tree and HEAD == `release`;
   - refuses output inside the workspace or over an existing file;
   - writes the zip via `git archive release`.

## 4. Invariants and where they hold

| Invariant | Enforced at | Status |
| --- | --- | --- |
| Agents cannot silently change approved checks | `_contract_unchanged` `pipeline.py:893-905`; `_host_checks` `:911-912` | Holds (tests: `test_validation.py`, `test_evidence_registry.py`) |
| A partial check subset is never release evidence | `verify_product` `release_eligible` needs `ids is None` (`validation.py:210`) | Holds |
| An agent's "verified" claim on a requirement is not trusted | `requirement_results` overwrites `status` (`validation.py:156-160`) | Holds |
| Release approval binds to the verified bytes | `decide()` `pipeline.py:1390-1399` (clean tree, HEAD, ledger, fingerprint, verifier) | Holds |
| Inputs changing during verification invalidate it | `_host_checks` `:913-926` | Holds |
| Symlinked tracked inputs are refused | `source_fingerprint` `validation.py:26-27` | Holds |
| Failed release checks cannot be approved | `decide()` `:1388` | Holds |
| **Legacy contracts are labelled as such at the gate** | `coverage: "legacy-unmapped"` is set (`validation.py:209`) but not shown in the release approval text (`pipeline.py:801-817`) or used by `decide()`/autopilot | **Gap (W1-F1)**: a contract with no requirements registry is `release_eligible` and the approver is not told. Observed in the synthetic trace. |
| **Every task gets at least one independent review** | `_checkers` + `org.pick(..., exclude=author)`; a checker that cannot be picked is skipped with `continue` (`pipeline.py:1229-1231`) | **Gap (W1-F2)**: if no checker can be staffed, the loop runs zero reviews and the task is marked done. Pinned by a new strict-xfail test. |
| Per-task security review | Only in `review_mode: thorough` (`_checkers`) | **Doc mismatch (W1-F3)**: README lines 9, 18 and 145 say every task gets a security review; the default `standard` mode runs code review + QA only |

## 5. Configuration-dependent behaviour

- **Review mode.** `pipeline.review_mode` is `standard` by default (`config.py:48`, validated `:113-115`). Small projects always use `light` and at most one rework (`pipeline.py:105-110`, `:1095`).
- **Desktop role switch.** In the desktop app (`create_app(desktop=True)`, `desktop.py:101`), `POST /api/desktop/switch` returns the other role's token (`server.py`, `desktop_switch`): one person holds both CEO and CTO. Since #10, autopilot there covers both roles. On the two-person dashboard it covers only the chooser's gates.
- **Autopilot.** `key` and `final` levels (`autopilot.py`); a release review under autopilot still requires audits, acceptance checks and executable verification to have passed. Sign-off is never automatic.

## 6. Human contributions required (not yet received)

| Owner | Needed for this document | Status |
| --- | --- | --- |
| Nikhil (architecture) | A decision record reviewing this architecture map and the W1-F1/W1-F2 invariants | **Not received** |
| Sanjana (AI workflow) | A synthetic requirements example with a requirements registry, and an explanation of requirement/test adequacy | **Not received** |

No human decision is recorded in this file until it is provided. Do not read the role table as authorship.

## 7. Limitations

- Mock runs exercise orchestration only. No real provider was called.
- The synthetic trace approves every gate by script; it shows the gate sequence and evidence linkage, not human judgement.
- Line numbers drift with every commit; re-anchor before citing.
