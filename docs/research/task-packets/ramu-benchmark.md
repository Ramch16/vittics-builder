# Ramu: benchmark protocol, metrics and budget

**Role in the plan:** benchmark and research owner.
**Time:** about 6–8 hours.
**Status:** all tasks pending.

## Read first

- `docs/research/benchmark-readiness-2026-10-31.md`
- `docs/research/benchmark-protocol-draft.md` and the Week 3 protocol revision draft (EB2-VISA folder, `Week03/01_Record/PROTOCOL-REVISION-DRAFT.md`)
- `docs/research/run-record.schema.json` (v2) and `vittics_builder/benchmarks.py` (`check_semantics`, `summarize_records`)
- `benchmark/schedule.py` and `benchmark/harness.py`

## Tasks

### R1. Reproduce the mock pilot

```
python -m benchmark.schedule --seed 20261031 | diff - benchmark/schedule-20261031.json && echo "schedule reproduces"
python -m benchmark.harness --schedule benchmark/schedule-20261031.json --out /tmp/r1
python -c "import json; s=json.load(open('/tmp/r1/summary.json')); print({c: (v['runs'], v['accepted_runs'], v['conditional_release_rate']) for c, v in s['by_condition'].items()})"
```

Expected: 48 runs, 0 accepted in both conditions, a multi-agent conditional release rate of 1.0 (mock
reviewers always approve), and 0 schema errors in `/tmp/r1/validation.json`.

**Deliverable:** your run's numbers and environment in `docs/research/reviews/ramu-week3.md`.

### R2. Approve or change the metrics and schema

Decide on schema v2 and the semantic rules (`check_semantics`): approve them, or list your changes. Check that the
primary metric (D12) and secondary metrics (false releases, rework, wall time, tokens, cost per accepted run)
are defined the way you want them reported. Also check that unknown cost can never be shown as zero.

**Deliverable:** a "Metrics and schema" section in your review file; code changes in a PR from your account.

### R3. Set the real-study parameters (D13)

Propose the model, provider, per-run caps (tokens, seconds, cost) and the aggregate budget for 48 runs. Base
the estimate on published per-token prices: list the source and date, and show the arithmetic. Include a
contingency and a stop rule.

**Deliverable:** a "Proposed freeze values" section, plus a filled-in copy of
`Week04/05_Coordination/EXPERIMENT-FREEZE-DRAFT.json` (EB2-VISA folder) with `spending_authorized` left `false`.
**Accepted when:** every null in the freeze draft has a proposed value or a stated reason it stays null.
Spending authorization is a separate decision for the whole team.

### R4. Runtime cap enforcement (needed before any paid run)

Caps are recorded today but not enforced. Specify, or build, a hard stop: the run ends when the summed tokens
or cost across all agents in a slot reach the cap, including in-flight requests. Then test it with the mock
provider.

**Deliverable:** a PR from your account with a test (for example, a mock run with a tiny cap ends as
`terminal_status: "incomplete"` with a recorded blocker), or a written specification if you don't build it.

### R5. Literature plan (Weeks 3–4)

List the related systems and papers to compare against, and say how each relates to this study's design
(start from `Week03/01_Record/RELATED-SYSTEMS-MATRIX.md`). Check every citation at its original source.

**Deliverable:** a section in your review file, or a separate document.
