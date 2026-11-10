# Measure delivery quality and cost

`vittics-builder benchmark PROJECT` exports recorded work. It deliberately does
not equate tracker completion with independent acceptance.

`vittics-builder benchmark-compare trials.json` summarizes externally evaluated
trials without loading a company, running agents, invoking commands, or spending
provider credits. It accepts observations from Vittics, Paperclip, or another
system. No comparative result is bundled with this change.

## Freeze three workloads

1. **Bug fix:** a starter repository with a reproducible empty-input crash.
   Independently check the crash is fixed and previous behavior still works.
2. **Authenticated CRUD:** a frozen brief for sign-in, create/edit/delete,
   authorization and persistence. Test separate users, denied access, restart
   persistence, invalid input, and a complete browser journey.
3. **Multi-component application:** a frozen brief with UI, API and database.
   Independently check clean installation, API/UI compatibility, migration of
   existing data, restart, and failure recovery using synthetic fixtures.

Prepare and retain the actual fixtures and acceptance suite before starting
trials. These are workload specifications, not supplied working applications or
an executed benchmark. Acceptance tests should be owned by the evaluator, outside
agent-editable workspaces. Retain commands, exit statuses, traces and defects in
the evidence location. A human override does not make failing acceptance pass.
Use dedicated credentials and synthetic data for real runs.

Run at least three fresh trials per system and workload. Freeze brief, starter
repository, acceptance suite, models, environment and comparison policy. Policy
includes budget, timeout, concurrency, human-assistance limits and cost accounting.
Hash their canonical files with SHA-256 and use the same hashes only when the
inputs really match. Include failed and timed-out runs, not just successful ones.
Record versions separately: they are the variable under test.

## Observation format

Use `{"schema_version": 1, "trials": [...]}`. Each trial has:

```json
{
  "id": "vittics-crud-01",
  "system": "vittics",
  "version": "exact-source-commit",
  "workload": "authenticated-crud-v1",
  "brief_sha256": "<64 lowercase hexadecimal characters>",
  "starter_sha256": "<64 lowercase hexadecimal characters>",
  "acceptance_sha256": "<64 lowercase hexadecimal characters>",
  "environment_sha256": "<64 lowercase hexadecimal characters>",
  "models_sha256": "<64 lowercase hexadecimal characters>",
  "policy_sha256": "<64 lowercase hexadecimal characters>",
  "started_at": "2026-11-09T10:00:00-05:00",
  "stopped_at": "2026-11-09T10:30:00-05:00",
  "status": "accepted",
  "independent_acceptance": true,
  "evidence": "retained-evidence/vittics-crud-01.json",
  "cost_usd": 2.5,
  "cost_basis": "estimated",
  "defects": 0
}
```

Replace placeholder digests with real hashes. `status` is `accepted`, `failed` or
`incomplete`; incomplete means the trial stopped before verified delivery. All
rows require independent evaluation, including the disposition of incomplete
runs. `defects` counts independently observed distinct defects under the fixed
acceptance criteria. Keep scope and observation period consistent across runs.

`cost_basis` is `billed`, `estimated` or `unknown`. Unknown cost must be `null`.
Subscription usage is not automatically free: define an allocation policy or
report unknown. Use the same policy for infrastructure and reviewer costs.
The report labels mixed cost bases rather than pretending they are invoices.

## Read the report

Only identical workload/input fingerprints share a cohort. Versions and system
names remain separate within it. Reports include acceptance rate, failures,
incomplete runs, defect counts, wall-time median/range, total known cost and
cost per accepted delivery. Failed/incomplete costs remain in the numerator.
With no accepted deliveries or any unknown cost, cost per accepted delivery is
null. Unmatched cohorts, unequal trial counts and small samples are flagged.
There is no automatic winner: three trials are exploratory, and matching hashes
and acceptance attestations are operator-supplied, not independently authenticated
by the reporting tool. Evidence references are never executed or dereferenced.

## Opt-in adaptive reviews

Set `pipeline.review_mode: adaptive` in `org.yaml` to select per-ticket reviewers
from actual changed paths and task descriptions:

- Plain documentation under `docs/`, or root README/CONTRIBUTING/CHANGELOG files:
  one reviewer. Executable examples and mixed changes retain standard review.
- Source, unknown changes and rework: code review and QA.
- Sensitive hints (authentication, secrets, payments, migrations, deployment,
  security, approval contracts): every staffed reviewer and QA role.

Renames include both old and new paths. Saved path evidence survives interrupted
reviews. Adaptive mode takes precedence over the small-project light shortcut.
The chosen level and reason are logged. This is a conservative heuristic, not a
security classifier; it cannot detect every sensitive change. Existing review
modes and defaults are unchanged. Existing release QA, audits and acceptance gates
are unchanged; small-project audit exemptions still follow existing policy.
Model routing now penalizes total recorded spend per reviewed success, including
failed attempts, instead of cost per evaluation. Unknown prices remain unknown.
Neither change establishes measured savings until the trials above are run.
