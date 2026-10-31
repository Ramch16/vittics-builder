# Missing-record checklist: human technical contributions

Prepared with AI assistance (Claude Code) on 2026-10-25. It lists **technical** records only. Credentials, work history, immigration and counsel material are out of scope and must stay out of this repository.

Roles are responsibilities, not code-author identities: Nikhil (architecture/provenance), Sanjana (requirements/workflow), Sai (security/reliability), Ramu (benchmarks/data). Nothing here is signed or decided for anyone. "Reported" means the user said it happened, and its contents have not been checked.

## Fields every record needs

**Artifact** (file, PR, commit or run) · **Date** (UTC) · **Decision or contribution, in the person's own words** · **Validation** (command or method, and the outcome) · **Reviewer** (who checked it) · **AI assistance** (what an AI produced or ran) · **Source revision**.

## Checklist

| Owner | Expected record | Artifact on hand | Date | Decision | Validation | Reviewer | AI assistance noted | State |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Nikhil | Week 1 architecture decision record (map accuracy; policies for A-01, A-02, S-08; baseline design; PR #10 acceptance) | Packet with AI-prefilled proposals (`Week01/03_Reviews`) | missing | missing (prefill is not a choice) | missing | missing | prefill labelled AI | **Reported, not checked** |
| Nikhil | Week 2 architecture/provenance claim trace (W2-N1/N2) | AI draft: `week2-claims.json` (architecture and provenance rows) | missing | missing | missing | missing | yes (this draft) | **Not started by owner** |
| Nikhil | GitHub approval on PR #10 from his own account | none | — | — | — | — | — | **Missing** |
| Sanjana | Week 1 requirements example and adequacy explanation | Packet with AI prefill | missing | missing | missing | missing | prefill labelled AI | **Reported, not checked** |
| Sanjana | Week 2 schema-v2 trace (W2-S1) | AI draft: `examples/requirements-v2/` | missing | missing | missing | missing | yes | **AI draft awaiting her review** |
| Sai | Week 1 independent reproduction (own commands, outcomes, scope) | Packet with AI prefill; no logs | missing | missing | missing (no own logs) | missing | prefill labelled AI | **Reported, not checked** |
| Sai | Week 2 environment/security disposition (W2-Q1/Q2) | AI drafts: `reproducibility-inventory.md`, claims S-01..S-13 | missing | missing | missing | missing | yes | **Not started by owner** |
| Sai | GitHub approvals on PRs #8–#10 from his own account | none | — | — | — | — | — | **Missing** |
| Ramu | Week 1 benchmark protocol decisions | Packet with AI prefill; protocol still draft | missing | missing | missing | missing | prefill labelled AI | **Reported, not checked** |
| Ramu | Week 2 baseline and metric semantics (W2-R1/R2) | AI drafts: `single-agent-baseline-spec.md`, schema v2, synthetic dry run | missing | missing | missing | missing | yes | **AI draft awaiting his review** |
| Ram | Identity facts for `thondapu lakshman` and machine-local author emails | none | missing | — | — | — | — | **Missing** |
| All four | Formal signatures | none | deferred to project end (user decision) | — | — | — | — | **Deferred** |

## AI contribution in Week 2 (Claude Code)

Claude restored the Week 1 bundle into an isolated clone and wrote every Week 2 file on `research/week2-readiness`. That includes the claims export, the readiness, reproducibility and baseline documents, the synthetic requirements example, the schema v2 semantics code and its tests. Claude also ran the dependency audits and the evidence capture. All commits are authored "Claude <noreply@anthropic.com>" with a Co-Authored-By trailer.
