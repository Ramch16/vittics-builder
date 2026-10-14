# Backlog implementation status

This branch begins the 21-item backlog. It does **not** complete all 21 items and is not a new desktop release. See `capability-audit.md` for the baseline and remaining acceptance criteria.

## Implemented in this branch

- **#1 inventory:** source/test mapping for all 21 proposals, with explicit gaps.
- **#2/#18 baseline telemetry foundation:** `vittics-builder --home COMPANY benchmark PROJECT --cutoff ISO_TIMESTAMP` exports metadata and recorded usage as JSON. It separates overlapping active time from summed agent time, and unknown costs from known totals. It does not run paid models or infer acceptance from Done status. Controlled trials and aggregate comparisons remain open.
- **#3/#4 repository intelligence foundation:** `vittics-builder repo-index PATH` returns Python symbols, import edges and content hashes. Add `--changed relative/path.py` to request advisory downstream test selection. Unknown files, dynamic code, unresolved dependencies and missing test links require a full suite. This is Python-only and not a complete API/schema/multi-language architecture graph. Release acceptance is never skipped.
- **#5 file-backed memory:** the `remember` tool accepts `evidence_files`. Recall excludes facts whose supporting files changed, disappeared or escape the project. Candidate worktree hashes are captured from the assigned workspace and only match the main workspace after integration. Existing memories without file evidence remain legacy unvalidated facts; this does not retroactively verify them.
- **#20 installer identity foundation:** desktop CI produces a separate manifest artifact containing source commit/tree, installer hashes/sizes, dependency-file hashes and build platform. This is not a signed attestation, SBOM, lifecycle test or reproducible-build proof.

## Remaining work (not checked off)

| Items | Remaining acceptance |
|---|---|
| 2, 18 | Repeated real-provider trials; missing cache fields; independent accepted-task/cost and regression reporting |
| 3, 4 | API/schema and multi-language graphs; impact integration beyond an advisory CLI |
| 5 | Automatic evidence binding, decisions/interfaces lifecycle and invalidation of legacy summaries |
| 6, 8, 9 | Process-kill recovery, side-effect idempotency, ownership race tests and conflict prediction |
| 7 | Enforced task interface contracts and ownership |
| 10 | Locked reproducible build/service environments |
| 11 | Independent requirement coverage and retained real-journey traces |
| 12 | Complete supported-version upgrade/rollback and interrupted migration matrix |
| 13 | Clean OS install, upgrade and uninstall verification |
| 14 | Independent threat-model/adversarial verification and audit dispositions |
| 15 | Cross-engine execution-policy conformance |
| 16 | Concurrent token reservation/overshoot and fallback accounting |
| 17 | Validated context/tool-result caching |
| 19 | Tested stack/provider compatibility profiles |
| 20 | SBOM/attestations, reproducibility and release rollback evidence |
| 21 | Repeatable ArtCraft-scale reference implementation and independent verification |

## Validation

New tests cover overlapping/interrupted runs, unknown cost, privacy of metadata exports, CLI output, transitive/relative imports, content invalidation, conservative fallback, symlink exclusion, evidence revalidation/reopening/candidate isolation and manifest integrity. Existing worktree, recovery, approved-runner and foundation regressions are also exercised. Record final command outcomes in the PR; do not treat this list as proof that unexecuted acceptance requirements passed.
