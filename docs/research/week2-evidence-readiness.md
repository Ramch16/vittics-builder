# Week 2 evidence readiness

Status: **draft prepared with AI assistance (Claude Code) on 2026-10-25.** No human decision is recorded in this file. Week 1 is administratively closed at Ram's direction; its verification and signatures are deferred to project end, and nothing here converts those deferred items into verified facts.

Machine-readable export: [`week2-claims.json`](week2-claims.json) (36 claims). The tables below are rendered from it.

## 1. Source identities

| Identity | SHA | Checked how |
| --- | --- | --- |
| Public `main` at Week 2 kickoff | `f01a108efddd741c9a4f1f6b62bb84215ef333aa` | `git fetch` 2026-10-25; unchanged since the Week 1 merges |
| Main CI run 40216707827 | on `f01a108` | REST: all 5 jobs `success` (dashboard-dialogs, Ubuntu 3.11/3.12, macOS 3.12, Windows 3.12). **Per-job counts not retrievable**: job logs redirect to a blob host blocked here |
| Week 1 research bundle | `research/week1-evidence` @ `f5fd58c50424d237c774cc60b732cb2f94532403`, tree `7954331b…` | Bundle SHA-256 `65a5e9b1…` verified on the user's Mac and here. Restored into a **fresh isolated clone**; descends from `main` |
| Week 1 result capture tested source | `abda17aff2a292cc96a244747997751771986ae9` | From the Week 1 manifest; differs from the bundle tip, which adds only evidence files |
| Week 2 work branch | `research/week2-readiness` (from `f5fd58c`), local only | See WEEK2-HANDOFF for the result SHA |
| Remote branches | 19 branches listed (complete listing, fewer than 100); **no `research/*` branch on GitHub** | REST `branches?per_page=100` |

## 2. Status vocabulary and counts

| Status | Claims | Meaning |
| --- | --- | --- |
| fixed_on_main | 2 | fix merged to public main with a passing test |
| fixed_on_local_branch | 1 | fix exists only on the unpublished research branch |
| expected_failure_known_gap | 6 | strict-xfail test proves the gap still exists |
| verified_by_ai_check | 8 | claimed behaviour held in an AI-operated check (not an independent human review) |
| untested_inference | 6 | from code reading or configuration only |
| documented_mismatch | 2 | docs and code disagree; proposed wording not applied |
| documented_limit | 1 | known limitation, intended or accepted pending review |
| partial_check | 1 | checked within a stated narrow scope only |
| open_gap | 2 | missing capability |
| draft_spec | 1 | specified, not implemented or approved |
| no_evidence | 1 | no data exists |
| unresolved_human_input | 1 | needs factual input from a person |
| user_reported_review | 4 | user reports a review occurred; contents not checked |
| verified_individual_decision | 0 | a person's actual decision, received and recorded (none yet) |

`verified_by_ai_check` means Claude ran the check. It is **not** Sai's independent review, and no claim is `verified_individual_decision`.

## 3. Highest-priority risks: isolation, secret access, Git metadata

1. **S-01 (SEC-01): agent shell commands reach company secrets in default local mode.** Proven by three strict-xfail tests. Fix proposal P-04 below.
2. **S-02 (SEC-05): writable `.git`, so a planted hook runs on the company's own commit.** Proven in **local mode only**. The Docker variant is an inference from the volume mount and was **not tested**: Docker's daemon was unavailable, and no live exploit cases were run. No Docker escape is claimed.
3. **A-01 (W1-F2 = W1-S2, one issue): tasks pass with zero independent reviews** when no checker can be staffed. Both Week 1 IDs refer to this single defect.
4. **S-03, S-07, S-08: secrets in other variable names; vault values seen by product code; read-only roles not enforced on CLI engines.**

## 4. Claims register

| ID | Week 1 IDs | Area | Claim | Source rev | Evidence | Observed | Status | Next action | Owner |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S-01 | SEC-01 | security | Agent shell commands in default local mode cannot reach company secrets (vault, saved API key) or system paths. | `f5fd58c` | tests/test_security_boundaries.py (3 strict xfails); evidence/week1/20261025T174908Z-abda17a/suite.log | Claim does NOT hold: `cd ..` chains, absolute paths and quoted system paths are not refused (tests xfail as designed). | **expected_failure_known_gap** | P-04: keep secrets outside the agent-reachable tree or make Docker the default for real providers; flip xfails when fixed. | Sai; Nikhil |
| S-02 | SEC-05 | security | Git metadata and hooks in the workspace cannot be altered by agent commands to run code on the host. | `f5fd58c` | tests/test_security_boundaries.py::test_agent_planted_git_hook_does_not_run_on_company_commit (strict xfail); evidence/week1/20261025T174908Z-abda17a/suite.log | Claim does NOT hold in local mode: a hook written by a command ran on the company's commit. write_file still refuses .git (passing test). | **expected_failure_known_gap** | P-05: run company git with core.hooksPath disabled and keep .git out of (or read-only in) the agent mount; acceptance test = the xfail passes in local and Docker mode. | Sai |
| S-03 | SEC-03 | security | Environment passed to agent commands contains no secrets. | `f5fd58c` | tests/test_security_boundaries.py::test_credentials_in_connection_urls_do_not_reach_commands (strict xfail) | Claim does NOT hold for secrets inside other names (DATABASE_URL with a password). | **expected_failure_known_gap** | Allowlist environment for agent commands (P-04 scope); acceptance = xfail passes. | Sai |
| S-04 | SEC-02 | security | CLI engines do not inherit dashboard tokens or other providers' keys. | `f01a108` | tests/test_engines.py::test_cli_engines_do_not_inherit_the_dashboard_tokens_or_other_keys; CI 5/5 on f01a108 | Holds with a stand-in CLI. | **fixed_on_main** | Smoke-test real logins (reported done by user in Week 1; record method/result). | Sai |
| S-07 | SEC-07 | security | Vault values reach only approved host checks and never persist in stored records. | `f5fd58c` | tests/test_week1_negative.py::test_vault_canary_reaches_checks_but_no_stored_record | Persistence part holds (canary absent from DB tables and VERIFICATION.json). Agent-written product code does receive the values by design. | **verified_by_ai_check** | Decide whether approval wording must state that product code sees the keys (SEC-07). | Sai; Nikhil |
| S-08 | SEC-08, reviewer-bash | security | Read-only roles on CLI engines are enforced read-only. | `f5fd58c` | tests/test_week1_negative.py::test_unverified_adapters_enforce_read_only_for_read_roles (5 strict xfails); ::test_claude_code_reviewer_gets_bash_but_not_edit_tools | Does NOT hold for the 5 unverified adapters (no read flag). Claude Code reviewers get Bash, which can write. | **expected_failure_known_gap** | Policy decision (Nikhil): disable unverified adapters by default and/or remove Bash from reviewers. | Nikhil; Sai |
| S-09 | SEC-06 | security | Hosted container isolates agent commands from server data. | `89694d5` | code reading only | Not tested. | **untested_inference** | Test in the container before any hosted use. | Sai |
| S-05 | SEC-04 | security | Autopilot cannot decide gates owned by the other human. | `f01a108` | tests/test_idea_to_production.py::test_autopilot_only_decides_for_whoever_chose_it; CI 5/5 | Holds on the mock provider. | **fixed_on_main** | Nikhil's written acceptance (user-reported only). | Nikhil |
| S-06 | W1-S1 | security | Git commands keep working inside agent commands when the host configures git via environment variables. | `f5fd58c` | tests/test_tools.py::test_git_config_environment_is_scrubbed_as_a_set | Holds on the research branch; fails on main (shown in Week 1). | **fixed_on_local_branch** | Review and PR when publication is authorized. | Sai |
| S-10 | SEC-09 | security | Docker sandbox limits resources and privileges. | `89694d5` | code reading only | Not tested (no Docker here). | **untested_inference** | Add --user/--pids-limit/--memory under P-05 with a test. | Sai |
| S-11 | SEC-10 | security | Dashboard and desktop surfaces are hardened (token handling, CSP). | `89694d5` | code reading only | Static tokens, no rate limit; CSP null. | **untested_inference** | Weeks 9–10 security tests. | Sai |
| S-12 | SEC-11 | security | Prompt-injection surfaces are controlled. | `89694d5` | none | Not tested. | **untested_inference** | Weeks 9–10 adversarial tests with synthetic payloads. | Sai |
| S-13 | SEC-12 | security | Stored prompts/logs and secrets are protected at rest. | `89694d5` | code reading only | Plaintext SQLite; secrets JSON mode 0600. | **untested_inference** | Decide on encryption-at-rest scope. | Sai |
| A-01 | W1-F2, W1-S2, zero-review | architecture | Every task receives at least one independent review before it is marked done. | `f5fd58c` | tests/test_week1_negative.py::test_no_task_is_done_without_an_independent_review (strict xfail) | Does NOT hold: with no reviewer or QA staffed, 4 tasks were marked done with zero reviews. | **expected_failure_known_gap** | Policy (Nikhil): fail closed or warn; then fix and flip the xfail. | Nikhil; Sai |
| A-02 | W1-F1, legacy-unmapped | architecture | The release approver is told when acceptance coverage is legacy-unmapped. | `f5fd58c` | tests/test_week1_negative.py::test_release_reviewer_is_told_when_requirements_are_unmapped (strict xfail); synthetic trace | Does NOT hold: legacy-unmapped contracts are release_eligible and the summary omits the label. | **expected_failure_known_gap** | Policy (Nikhil): block, warn or accept; then fix and flip the xfail. | Nikhil; Sanjana |
| A-03 | — | architecture | Release and sign-off approvals bind to a clean tree, verified HEAD, release-eligible ledger row, source fingerprint and verifier identity. | `f01a108` | tests/test_evidence_registry.py (missing/failed ledger, mid-check change); synthetic trace | Holds. | **verified_by_ai_check** | Human confirmation (Nikhil). | Nikhil |
| A-04 | — | architecture | Agents cannot change approved acceptance checks without a CTO decision. | `f01a108` | tests/test_approved_runner.py::test_changed_contract_blocks_both_runner_paths; test_evidence_registry.py::test_registry_change_requires_approval | Holds. | **verified_by_ai_check** | Human confirmation (Nikhil). | Nikhil |
| A-05 | — | architecture | A partial check subset is never release evidence; agent-asserted requirement status is ignored. | `f5fd58c` | tests/test_evidence_registry.py; tests/test_requirements_example.py | Holds. | **verified_by_ai_check** | Sanjana's review of the example. | Sanjana |
| A-06 | W1-F3 | architecture | Per-task security review happens on every task (README lines 9, 18, 145). | `89694d5` | code reading | Does NOT hold by default: standard mode runs code review + QA; security review only in thorough mode. | **documented_mismatch** | Apply the proposed README wording after review. | Nikhil |
| A-07 | — | architecture | Validation detects weak (always-passing) checks. | `f5fd58c` | tests/test_requirements_example.py::test_weak_check_is_accepted_by_the_validator | Does NOT hold: 'true' is accepted. Documented limit. | **documented_limit** | Rely on CTO review of product.json and the hidden oracle; record as a limit. | Sanjana; Nikhil |
| P-01 | — | provenance | Bundled skills/karpathy-guidelines.md is upstream CLAUDE.md with its title removed and a front-matter header added. | `f5fd58c` | Week 1 comparison against forrestchang/andrej-karpathy-skills @ 2c60614 (CLAUDE.md last changed 8462496) | Holds (byte comparison of the body). | **verified_by_ai_check** | Human decision on the notice wording. | Nikhil |
| P-02 | — | provenance | No code, prompts or assets were copied from other agent-office projects (NOTICE). | `89694d5` | none | Not tested (no similarity scan). | **untested_inference** | Decide whether to run a similarity check; keep the claim narrow. | Nikhil |
| P-03 | — | provenance | NOTICE covers what desktop installers distribute. | `89694d5` | code reading | Does NOT hold: PyInstaller/CPython and 422 Rust crates not listed. | **documented_mismatch** | Generate a per-release license inventory. | Nikhil |
| P-04 | — | provenance | Every author identity in git history is mapped to a person. | `89694d5` | Week 1 history analysis | Does NOT hold: 'thondapu lakshman' and machine-local Ram identities unresolved. | **unresolved_human_input** | Factual confirmation from the people involved; no history rewrite. | Ram; Nikhil |
| R-01 | — | reproducibility | Main f01a108 passes CI on all targets. | `f01a108` | GitHub run 40216707827 job conclusions (REST), retrieved 2026-10-25 | All 5 jobs success. | **verified_by_ai_check** | — | Sai |
| R-02 | — | reproducibility | The browser test subset passes in a CI-equivalent environment. | `abda17a` | Week 1 captures: baseline 20261025T173648Z-f01a108 (1 failed, mcp 2.3.0 outside <2) and result 20261025T174908Z-abda17a (38 passed, 1 skipped) | Passes without mcp; fails with mcp 2.3.0. | **verified_by_ai_check** | Pin mcp<2 in the browser environment or adapt integrations.py to mcp 2.x. | Sai |
| R-03 | — | reproducibility | Dependencies are locked for reproducible setup. | `f5fd58c` | reproducibility-inventory.md | Does NOT hold: no lockfile; a resolved-version snapshot exists for this capture only. | **open_gap** | P-06 lockfile + clean-environment test. | Sai; Ramu |
| R-04 | — | reproducibility | Resolved Python dependencies have no known published vulnerabilities. | `research/week2-readiness` | 05_Coordination/evidence dependency-audit outputs | PyPI service: no known vulnerabilities for 30 (dev) and 33 (dev+browser) pinned packages. OSV service: blocked (proxy 403). | **partial_check** | Run OSV and cargo/npm audits where network allows. | Sai |
| B-01 | — | benchmark | A matched single-agent baseline exists. | `f5fd58c` | single-agent-baseline-spec.md (draft) | Specified as a draft; not implemented. | **draft_spec** | Nikhil/Ramu decisions; then implement P-08. | Nikhil; Ramu |
| B-02 | — | benchmark | Run records enforce accepted-only-with-independent-oracle, null unknown cost, ordering, unique IDs and caps. | `research/week2-readiness` | tests/test_benchmarks.py; synthetic dry run (12 valid, 10 broken variants all caught) | Holds on synthetic records. | **verified_by_ai_check** | Ramu approves or changes the schema. | Ramu |
| B-03 | — | benchmark | Multi-agent improves acceptance or reliability over single-agent. | `—` | none | No real-model data exists. | **no_evidence** | Weeks 3–4 protocol approval; no paid runs until then. | All four |
| B-04 | — | benchmark | Subscription CLI usage is recorded as unknown cost. | `f01a108` | code reading (Week 1) | Does NOT hold: recorded as a known $0 (priced=1). | **open_gap** | P-07 database change. | Ramu |
| H-01 | — | human | Nikhil's architecture decision record. | `—` | User report | Reported completed; contents not checked; packet holds AI-prefilled proposals. | **user_reported_review** | Supply confirmed choices, date, reviewed revision. | Nikhil |
| H-02 | — | human | Sanjana's requirements example and adequacy explanation. | `—` | User report | Reported completed; contents not checked; Week 2 example is AI-assisted. | **user_reported_review** | Confirm or rewrite the example; record decisions. | Sanjana |
| H-03 | — | human | Sai's independent security reproduction. | `—` | User report | Reported completed; no reproduction logs received. | **user_reported_review** | Provide own commands, outcomes, scope. | Sai |
| H-04 | — | human | Ramu's benchmark protocol sign-off. | `—` | User report | Reported completed; protocol remains draft. | **user_reported_review** | Confirm choices; approve schema v2 or request changes. | Ramu |

## 5. Unresolved policy decisions (no confirmed human decision has been supplied)

| Decision | Options on record | Owner | Status |
| --- | --- | --- | --- |
| Legacy-unmapped contracts at release (A-02) | block / warn at the gate / accept | Nikhil (input: Sanjana) | **Unresolved.** The Week 1 packet holds AI-prefilled proposals, not choices |
| Tasks with no available reviewer (A-01) | fail closed / warn and flag at release | Nikhil (input: Sai) | **Unresolved** |
| Reviewer `Bash` on CLI engines (S-08) | accept and document / read-only copy / remove Bash | Nikhil | **Unresolved** |
| Unverified CLI adapters (S-08) | disable by default / warn | Nikhil, Sai | **Unresolved** |
| Single-agent baseline design (B-01) | see `single-agent-baseline-spec.md` | Nikhil, Ramu | **Draft only** |
| Run-record schema v2 (B-02) | approve / change | Ramu | **Draft only** |

## 6. Narrow remediation proposals with acceptance tests (not implemented in Week 2)

| ID | Smallest change | Acceptance test (already in the repo) | Notes |
| --- | --- | --- | --- |
| P-04a | Move `.vittics/` secrets (vault, `credentials.json`) outside the agent-reachable tree, or refuse local mode with a real provider unless explicitly allowed | `tests/test_security_boundaries.py` vault/credential xfails pass; marker removed | Highest priority |
| P-05a | Run every company git call with `-c core.hooksPath=/dev/null` (and refuse repository-level `core.fsmonitor`/`core.sshCommand`) | `test_agent_planted_git_hook_does_not_run_on_company_commit` passes | Small, local-mode fix |
| P-05b | Mount the workspace into Docker without a writable `.git` | New Docker-mode test on a host with a daemon (Sai) | Needs Docker environment |
| P-04b | Allowlist the environment for agent commands instead of name-based removal | `test_credentials_in_connection_urls_do_not_reach_commands` passes | May break agent tooling; needs review |
| A-01 fix | In `_run_task`, if no checker reviewed the task, pause and raise a CTO staffing approval instead of passing | `test_no_task_is_done_without_an_independent_review` passes | Only after Nikhil chooses "fail closed" |
| A-02 fix | Show `coverage: legacy-unmapped` in the release and sign-off summaries (and block, if chosen) | `test_release_reviewer_is_told_when_requirements_are_unmapped` passes | Policy first |
| R-02 fix | Enforce `mcp<2` in the browser job, or adapt `integrations.py` to mcp 2.x | MCP stdio test passes with mcp 2.x, or the environment pins <2 | |
| P-06 | Lockfile with hashes, used by CI | Clean install from the lockfile reproduces the suite counts | |

## 7. Requirements and benchmark readiness

- **Synthetic schema-v2 requirements example (AI-assisted):** `examples/requirements-v2/`. It has 6 requirements mapped to 8 checks, 7 variants (5 rejected, 1 claim ignored, 1 documented weak-check limit) and manual-only limits. Every check command is labelled `PLANNED-NOT-IMPLEMENTED`. It is Sanjana's only after she confirms or rewrites it.
- **Matched single-agent baseline:** `single-agent-baseline-spec.md`, a draft that is not implemented and not approved.
- **Schema v2 and semantics:** `run-record.schema.json` v2 adds the oracle reference and caps.
    - `benchmarks.check_semantics` enforces the rules: accepted requires an independent nonempty all-passing oracle; unknown or unpriced cost is null; end follows start; run IDs are unique; caps are enforced across all agents and retries; tree and oracle references are present; incomplete runs are kept.
    - The summary separates the **overall** release-and-oracle success (over all runs) from the **conditional** release rate (among runs that reached a release decision).
    - Cost per accepted run stays undefined at zero acceptance.
    - All records used are `data_kind: synthetic`.

## 8. Environment and verification

See `reproducibility-inventory.md` and the Week 2 evidence capture (manifest, logs, audit outputs). The Week 1 baseline browser failure (mcp 2.3.0) and the later isolated passing subset are both retained. They ran in different environments and are not a comparison.
