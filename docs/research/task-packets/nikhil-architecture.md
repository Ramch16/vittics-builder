# Nikhil: architecture, review policy and baseline design

**Role in the plan:** architecture and orchestration owner.
**Time:** about 4–6 hours.
**Status:** all tasks pending.

## Read first

- `docs/research/decisions-2026-10-31.md`: decisions D1–D5, D8 and D11 sit in your area. Ram decided them;
  you haven't reviewed them yet.
- `vittics_builder/pipeline.py`: `min_reviews`, `_checkers`, `_run_task` (review loop) and the release approval
  (search for `legacy-unmapped`).
- `vittics_builder/agent.py`: search for `decision D4`.
- `vittics_builder/engines.py`: `run_cli`, search for `SEC-08`.
- `benchmark/harness.py` and `docs/research/single-agent-baseline-spec.md`.

## Tasks

### N1. Review the policy changes (D1–D5)

```
python -m pytest -q -p no:cacheprovider tests/test_week1_negative.py tests/test_engines.py tests/test_models.py
git diff research/week2-readiness fix/review-and-isolation-policies -- vittics_builder/pipeline.py vittics_builder/agent.py vittics_builder/engines.py
```

For each of D1–D5, decide whether to **confirm**, **amend** or **reject** it, and give a reason. Things to look at:
- D1: is stopping the whole build right, or should only that ticket block while others continue?
- D2: should a small project in light mode need 1 review? Should thorough mode need exactly 2, or all staffed reviewers?
- D4: reviewers without a shell can't run tests themselves. Is host-run `run_approved_checks` enough?
- D5: refusing is strict. Would a warning plus a dashboard label be better for desktop users?

**Deliverable:** a GitHub review on the fix PR, plus a "Policy decisions" table in
`docs/research/reviews/nikhil-week3.md` (ID, confirm/amend/reject, reason, date).
**Accepted when:** all five rows are filled, and any amendment comes with a code change or an issue.

### N2. Check the baseline matches the design (D11)

Run one slot of each condition and read what each condition received:

```
python -m benchmark.harness --schedule benchmark/schedule-20261031.json --out /tmp/n2 --slots 1-2
python -c "import json; [print(json.loads(l)['condition'], json.loads(l)['hashes']) for l in open('/tmp/n2/records.jsonl')]"
```

Compare `harness.py` (`run_slot`) with `single-agent-baseline-spec.md` §3. List every difference in inputs,
tools, prompts, attempt limits and stopping rules between the two conditions, and decide whether each one is
acceptable.

**Deliverable:** a "Baseline interface" section in your review file, with each difference either accepted (and
why) or marked as a fix needed (as an issue).
**Accepted when:** both conditions' prompt hashes and attempt limits have been checked by you, and the list
names at least the known difference: single_agent gets public-test output as feedback, while multi_agent gets
reviewer findings.

### N3. Architecture map confirmation

Confirm or correct the architecture map in `docs/research/week1-audit.md` §2 against the current code
(pipeline stages, roles, engines, sandbox modes). Note what changed with this branch: the review minimums,
reviewers without a shell, and the sandbox backend.

**Deliverable:** corrections in a PR, or "confirmed as of <commit>" in your review file.

### N4. Open architecture items (pick at least one)

- P-05b: Docker mode mounts a writable `.git`. Propose a mount layout (for example, a `.git` mounted read-only or
  kept outside the mount) with a test.
- Show the active sandbox mode (`sandbox_backend()`) on the dashboard and in `vittics-builder doctor`.

**Deliverable:** a PR from your account with the change and a test, or a written design if you don't have
time to build it.
