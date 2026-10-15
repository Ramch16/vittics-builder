# Assurance implementation

This is an incremental implementation of the six-phase assurance proposal. No phase is claimed complete solely because code was added.

## Acceptance ledger increment

Newly generated `product.json` contracts use `schema_version: 2`. They declare a nonempty `requirements` array. Each requirement has a unique `id`, nonempty `description`, `risk` (`low`, `medium`, `high`) and nonempty `required_checks` referencing actual check IDs. Registry changes require renewed contract approval. A claimed status in the contract is ignored: observed check results determine the report's status.

Legacy contracts remain supported and reports explicitly say `coverage: legacy-unmapped`. This is compatibility, not proof that all PRD requirements are covered. Migrating an existing contract requires a reviewed registry; the system does not invent requirements from prose.

Full host verification saves its result in the company database's `verification_runs` table, outside the product workspace. Release approval carries the record ID, and CEO signoff inherits it. Missing, failed, source-stale or verifier-stale records block approval. Existing pending release/signoff approvals without a ledger ID must be rejected and acceptance rerun. Do not fabricate a record for an old approval.

The fingerprint covers tracked file paths, contents and executable bits, including documentation and configuration. Symbolic links fail closed. Only the generated `docs/VERIFICATION.json` is excluded to avoid self-reference. Source changes during verification invalidate the run. All changes committed by QA/audits trigger another full run; there is no blanket `docs/` exemption. The record also identifies the verifier implementation, Python and platform. Partial check runs cannot qualify for release.

The workspace JSON remains a human-readable report, not the authority for approval. Database storage is a separation from workspace editing, **not** an operating-system security boundary against processes with unrestricted access to the company database. External services, ignored files, installed dependencies and environment variables are not fully fingerprinted yet. Requirement completeness and the adequacy of test implementations still need independent review.

## Remaining work

1. Acceptance: independent completeness checking; protected test/policy inputs; dependency/environment fingerprints; manual requirement evidence with authorized identities; artifact identity enforcement.
2. Contracts: approved interface schemas, file/database ownership and migration compatibility enforced at integration.
3. Intelligence: JS/TS/API/schema/configuration graphs, manifest resolution and safe automatic test execution selection.
4. Recovery: durable execution leases, general side-effect idempotency, interrupted-merge recovery and process-kill/concurrency stress tests.
5. Security: mandatory risk-based scanners and authorization tests, isolated credentials, threat models and review dispositions.
6. Benchmarks: repeated clean-environment representative builds, independent verification, raw metrics and statistical summaries.

Existing repair reservations, worktrees, conservative Python impact analysis and benchmark exports remain in place. This increment does not replace them or claim they satisfy all remaining acceptance criteria.

## Local validation, 2026-10-15

- Full regression suite after granting loopback access: **367 passed, 8 skipped**. The earlier restricted run had 12 failures/errors associated with local-server execution; the affected test files subsequently passed (43 tests).
- A subsequent frozen-desktop identity adjustment initially produced three false stale-evidence failures. Replacing interpreter serialization with a deterministic code representation fixed them. On the final code, the evidence-registry, validation and pipeline suites passed: **48 passed**. The full suite was not repeated after this final identity-only correction.
- Tests include missing/invalid requirement mappings, claimed success with failed evidence, registry approval protection, partial-run exclusion, documentation-source invalidation, missing/failed database evidence, source mutation during a successful command, and operation without a loose Python source file.
- No paid model benchmarks, desktop installer lifecycle tests or independent security certification were performed by this increment. No release or installation was made.
