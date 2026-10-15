# Capability audit and implementation sequence

Audit date: 2026-10-14. Baseline: v0.25.0, built commit dc469e44d7b4369214a188ffe73de625f770a2c0. This is a source inspection, not a new execution benchmark. Existing tests below are evidence of coverage intent; they were not rerun for this documentation change. The release CI passed previously. No item is declared complete solely because a module or test exists.

## Inventory against the proposed 21 items

“Partial” means an implementation exists but does not establish the entire requested capability. “Not found” means not identified in this inspection, not proof that no related code exists.

| # | Capability / priority | Existing implementation and tests | Gap and acceptance required |
|---|---|---|---|
| 1 | Capability inventory / P0 | This inventory; `docs/workflow-reliability.md` describes v0.25 limits. | Initial inventory delivered; deepen module-level measurements as each slice is implemented. |
| 2 | Repeatable baseline / P0 | `runs.py`, `costs.py`, `telemetry.py`; mock workflow tests in `test_process_speed.py`. | Partial: no controlled, repeated real-provider benchmark found. Use the protocol below before claiming savings. |
| 3 | Repository index / P1 | `tools.py` file listing/reading and `sources.py` repository acquisition. | No symbol/import/API/schema dependency graph found. Fixture graph must handle edits, deletions, generated files and unsupported languages explicitly. |
| 4 | Change impact / P1 | `validation.py:verify_product(ids=...)` supports selected checks. | Selection is explicit, not inferred dependency impact. Prove downstream selection against known fixtures; unknown impact must fall back to full checks. |
| 5 | Persistent knowledge / P1 | `memory.py`, SQLite FTS and provenance; `test_foundations.py` persistence/scope tests. | Partial: lexical memory has no file/config dependency invalidation. Changed evidence must invalidate summaries and prevent stale injection. |
| 6 | Isolated parallel work / P1 | `tools.py` worktrees/merge; `pipeline.py`; `test_parallel.py` parallelism, single-owner execution and conflict tests. | Extend existing implementation. Verify process-kill recovery and concurrent ownership races before claiming full reliability. |
| 7 | Contract-first coordination / P1 | `validation.py` plan DAG and product checks; `test_validation.py`. | Partial: acceptance prose and role validation do not enforce shared API/schema contracts or file ownership. Add interface mismatch fixtures. |
| 8 | Durable recovery / P1 | `runs.py` persistent run events; pipeline review checkpoint; `test_process_speed.py` interrupted-review/parallel tests. | Partial: reviewer resumption is not universal tool replay safety. Fault injection before/after durable writes and side effects must prove deduplication. |
| 9 | Adaptive scheduling / P1 | Pipeline dependency scheduling, parallel limits and merge handling; `test_parallel.py`. | Partial: inspect conflict prediction and post-merge validation behavior before changing scheduling. Demonstrate independent overlap and conflicting-task serialization. |
| 10 | Reproducible environments / P1 | Workspace Docker mode, machine preflight, CI and product setup contract. | Partial: floating Python requirements and latest CI OS/stable Rust are not reproducible pins. Verify fresh provision with locked dependencies and isolated deterministic service fixtures. |
| 11 | End-to-end acceptance / P1 | `validation.py` executable product checks and `docs/VERIFICATION.json`; approved host runner; browser CI. | Partial: arbitrary project checks are author-defined. Require requirement coverage and retained real traces; fail deliberate broken-journey fixtures. |
| 12 | Migration/upgrade tests / P1 | `db.py:_migrate`; existing-company memory migration fixture in `test_foundations.py`. | Partial: no complete supported-version upgrade/rollback matrix established. Test old DB snapshots, interrupted migration and preserved data. |
| 13 | Desktop lifecycle / P1 | Desktop workflow builds macOS/Windows; backend smoke tests and macOS signature integrity checks. | Partial: build success does not prove clean install, upgrade, uninstall or settings preservation. Execute lifecycle tests on clean target systems. |
| 14 | Independent security / P1 | `security.py` scanning/dependency entry points; permission tests and reviewer roles. | Partial: role independence is not a completed adversarial audit. Threat model and negative tests must demonstrate boundaries and disposition findings. |
| 15 | Unified permissions / P1 | Engine read/write levels, Workspace controls and approved runner; `test_approved_runner.py`. | Partial: host runner and engine sandboxes are different enforcement layers. Build an engine/action policy matrix and test denied/approved paths without widening default access. |
| 16 | Budgets and routing / P1 | `costs.py`, `routing.py`, `failover.py`; budget tests in `test_operations.py`, routing tests in `test_foundations.py`. | Partial: spend limits and routing are not demonstrated hard per-task token reservations across concurrent calls. Test overshoot bounds, unknown pricing and fallback accounting. |
| 17 | Context/result cache / P2 | Provider cached-token usage is parsed in `engines.py`; persistent memory exists. | No general validated tool-result cache found. Cache reads only initially, keyed by content/config/tool versions; never replay mutations from a cache hit. |
| 18 | Quality/cost telemetry / P1 | `telemetry.py`, run records, review scores and routing outcome metrics. | Partial: no repeatable cross-release cost-per-accepted-task/regression report established. Preserve unknown costs and distinguish reviewer scores from observed defects. |
| 19 | Compatibility profiles / P2 | Linux/macOS/Windows Python CI; macOS/Windows packaging; `platforms.py`. | Partial: framework/provider profile coverage is not established by OS CI. Publish a bounded supported-profile matrix with actual outcomes. |
| 20 | Release provenance / P2 | v0.25 artifact hashes, CI builds and source identity; production rollback tests in `test_production.py`. | Partial: manual hashes are not automated provenance or bit-reproducible builds. Manifest must link source, dependencies, artifacts and evidence; test rollback. |
| 21 | ArtCraft-scale reference / P1 | Calculator/support trials and mock idea-to-production tests are related evidence only. | No repeatable multi-module reference benchmark found. Specify a fixed workload, independently verify delivery and repeat on fresh environments. |

## Dependency-ordered work

1. **Baseline harness and metric semantics:** extend existing run/usage records, export comparable observations, add missing-value handling and fixture tests. Do not initiate paid project runs implicitly.
2. **Repository intelligence:** content-hashed index, evidence invalidation, then conservative impact selection. Preserve full acceptance gates for releases.
3. **Execution reliability:** strengthen existing ownership/checkpoints with fault-injection evidence; introduce contracts and conflict-aware scheduling only for confirmed gaps.
4. **Verification:** locked environments, upgrade fixtures, desktop lifecycle, adversarial checks and automated provenance.
5. **Efficiency:** task token reservations, measured routing and validated read caching, compared to the baseline.
6. **Reference workload:** multi-module application trials with independent acceptance. Do not represent a mock pipeline run as product delivery.

Each implementation slice must name the existing module being extended, the observed gap, executable acceptance cases, required environment and evidence path. Check it off only after those cases pass. A blocked execution is a recorded blocker, not a passing result. No new release is implied by this audit.

## Repeatable baseline protocol (specified, not yet executed)

- Freeze prompt, acceptance requirements, visual-design approval, starter repository, synthetic fixtures, model IDs, provider settings, concurrency and machine/service versions. Compare v0.24 and v0.25 only under matching settings; retain intentional differences as experimental variables.
- Use a simple calculator, a CRUD application with authentication/database, and a multi-module reference application. Run at least three fresh independent trials per version/workload initially; report all failures and raw observations. Three trials are exploratory, not statistical proof.
- Record run ID, source/tree hash, start/end UTC, approval/usage-limit/runner-block intervals, run intervals, attempts, acceptance verdicts, artifact hashes and evidence locations. Stop at a declared terminal outcome or fixed timeout; include incomplete runs.
- Report elapsed wall time, active interval union (overlaps count once), summed agent time, and waiting time separately. Approval delays and provider outages must not be silently subtracted from total time.
- Preserve provider input, output, cache-read and cache-write fields separately where available. Mark unavailable components null. Existing combined token totals cannot be treated as equivalent billed tokens across providers. Record price schedule/source date and distinguish estimated, billed and unknown cost; zero is not a substitute for unknown.
- Define retry as another attempt at the same task; classify builder rework, reviewer retry and infrastructure retry separately. Define accepted tasks using explicit verdicts, and report human overrides separately from passing verification.
- Count observed defects using fixed acceptance tests and independent review, deduplicated by cause. Report post-acceptance regressions separately. Release success means the declared installer/application lifecycle and user journeys pass, not simply that all tickets are Done.
- Emit raw JSON observations and a summary with medians, ranges, sample counts, completion/release rates, retries, defects and cost per accepted task. With zero accepted tasks, cost per accepted task is undefined. Include failed-run costs in aggregate comparisons.
- Benchmark harness acceptance: fixtures covering overlapping runs, missing prices, cached usage, interrupted trials, human override, zero accepted tasks and mixed provider records must produce expected metrics. Validate deterministic exports and redact credentials/prompts containing sensitive data.

No runtime, token-saving or cost-saving percentage has been measured by this audit. Existing calculator observations are uncontrolled historical trials and must not become a claimed baseline.
