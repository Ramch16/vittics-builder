# Sanjana: requirements and task adequacy

**Role in the plan:** requirements and test adequacy owner.
**Time:** about 5–7 hours.
**Status:** all tasks pending.

## Read first

- `benchmark/README.md` and each `benchmark/tasks/T0n-*/spec.md` (requirements R1–R6 per task).
- `benchmark/oracle.py`: how hidden tests are run.
- `docs/research/examples/requirements-v2/`: the Week 2 sample contract with its open questions.

## Tasks

### S1. Requirement-to-check mapping for T01–T08

For each task, map every requirement (R1, R2, ...) to the public or hidden tests that check it.

```
python -m benchmark.oracle validate > /tmp/validate.json      # must report all_valid: true
grep -n "def test_" benchmark/tasks/T0*/starter/tests/test_public.py benchmark/tasks/T0*/hidden/test_hidden.py
```

**Deliverable:** `docs/research/reviews/sanjana-week3.md` with one table per task (requirement → test names →
"covered", "partly covered" or "not covered").
**Accepted when:** every requirement of all 8 tasks has a row, and every gap is listed.

### S2. Try to fool the oracle (adequacy test)

For at least 4 tasks, write a plausible but **wrong** implementation: one that passes the public tests but
breaks a requirement. Run it through the oracle and record whether the hidden tests catch it.

```
mkdir -p /tmp/s2 && cp -r benchmark/tasks/T03-inventory-reservations/starter /tmp/s2/T03
# edit /tmp/s2/T03/app/inventory.py with your wrong-but-plausible version
python -m benchmark.oracle evaluate T03 /tmp/s2/T03 | python -c "import json,sys; r=json.load(sys.stdin); print(r['all_passed'], [c['id'] for c in r['checks'] if not c['passed']])"
```

**Deliverable:** a table in your review file (task, the bug you planted, caught yes/no, by which test). For
each bug that got through, a PR adding a hidden test that catches it, together with a check that the reference
still passes (`python -m benchmark.oracle validate`).
**Accepted when:** at least 4 tasks are tried, and every bug that got through has a new test or an issue.

### S3. Difficulty and fit

Rate each task as small, medium or multi-module, and say whether it suits a fair comparison. Watch for anything
where a single builder or a review loop gets an unfair advantage. Suggest replacements if needed.

**Deliverable:** a "Task set" section in your review file, with your recommendation to Ramu (keep all 8, or
swap named tasks).

### S4. Week 2 requirements example

Answer the four open questions in `docs/research/examples/requirements-v2/README.md` in your own words, or
replace the example with your own.

**Deliverable:** a PR or a section in your review file.
