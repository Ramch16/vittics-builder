# Synthetic schema-v2 requirements example (AI-assisted draft)

**Status: AI-assisted (Claude Code), synthetic, not a human contribution.** It was prepared for Sanjana (requirements/workflow) to review, correct or replace. It becomes her contribution only when she confirms or rewrites it and that confirmation is recorded with a date. The product is invented, and no customer data is involved.

## Contents

| File | What it shows |
| --- | --- |
| `product.json` | A valid schema-v2 contract for an invented "Leave Ledger" library: 6 requirements mapped to 8 checks |
| `variants/*.json` | Deliberately broken or misleading copies, each with a `_variant_note` saying what the code does with it |

## The check commands are planned, not implemented

Every `command` in `product.json` starts with `PLANNED-NOT-IMPLEMENTED:`. No product code or tests exist for this example, so **no check has passed**. Running the contract as-is would fail every check, and that is the correct outcome.

The tests in `tests/test_requirements_example.py` exercise the mapping logic instead. They swap each command for a stand-in that exits 0 or 1 in a temporary folder, and they are labelled synthetic.

## Requirement → check mapping

| Requirement | Risk | Checks | Notes |
| --- | --- | --- | --- |
| REQ-001 submit a pending request | medium | submit-request | |
| REQ-002 reject end-before-start | medium | reject-invalid-dates | negative case |
| REQ-003 decide once | high | decide-request, no-double-decision | two checks; both must pass |
| REQ-004 balance arithmetic, floor at zero | high | balance-arithmetic, balance-floor | two checks |
| REQ-005 manager scope | high | decide-request, manager-scope | shares `decide-request` with REQ-003: one failing check unverifies both |
| REQ-006 persistence across restarts | medium | persistence-roundtrip | checks must start their own isolated instance |

## Variants and what the code does

| Variant | Result | Why it matters |
| --- | --- | --- |
| `unknown-check-id` | rejected | A typo in a check id cannot silently leave a requirement unmapped |
| `requirement-without-checks` | rejected | Every requirement needs executable evidence |
| `duplicate-requirement-id` | rejected | Ids must be stable and unique |
| `bad-risk` | rejected | Risk is low, medium or high |
| `v2-without-registry` | rejected | A v2 contract must carry the registry (v1 contracts fall back to `legacy-unmapped`, finding W1-F1) |
| `agent-claims-verified` | accepted, claim ignored | `requirement_results` recomputes status from actual check outcomes |
| `trivial-always-pass-check` | **accepted (limit)** | The validator cannot tell a weak check from a real one. Human review of `product.json` and the benchmark's independent hidden oracle are the safeguards. |

## Requirements that automated checks here do not establish (manual-only limits)

- Usability of the request and approval flow: needs a usability review with real users. Record it as manual evidence, not a check.
- Accessibility (keyboard use, screen readers, contrast): needs an accessibility review; out of scope for a library-level check.
- Legal and policy correctness of leave rules (jurisdiction, contracts): needs a policy owner's sign-off.
- Security beyond REQ-005's scope check (authentication, audit logging): not covered by this contract.
- Working-day calendars and public holidays: REQ-004 covers weekends only. Holidays are excluded unless a requirement is added.

## Open questions for Sanjana (her decisions; not answered here)

1. Is this mapping honest, or do any checks claim more than they exercise?
2. Should high-risk requirements need two independent checks?
3. How should manual-only evidence be recorded beside `product.json`?
4. What should the release gate do with legacy-unmapped contracts (finding W1-F1)? Nikhil owns the final policy.
