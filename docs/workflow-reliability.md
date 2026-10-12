# Workflow reliability corrections

Changes motivated by the two calculator trials:

- Agent-created proposals during requirements/design remain in backlog. The architect submits the scheduled plan after considering these proposals, instead of automatically running both sets of tickets. Explicit human requests retain their existing scheduling behavior.
- Every project assignment receives recent recorded approval decisions. These supersede stale pending-approval text; they do not substitute for test evidence.
- CLI capacity and temporary-unavailability errors enter the existing engine-unavailable/failover path, including errors on stderr after partial stdout.
- Builder output is committed and checkpointed before review. When the tracked candidate tree is unchanged and the workspace is clean, a resumed task retries review without invoking the builder again. Changed candidates are rebuilt/reviewed normally. Missing verdicts pause review without charging builder rework or scoring the builder.
- Release integration must submit a nonempty structured acceptance checklist. Failed or unverified entries cannot accompany an approval. The checklist is reported evidence, not independent proof of completeness or execution; human review remains necessary.
- The shared live-stage label is Running, not Live in production. The existing deployment record continues to distinguish local preview from other environments.

These changes do not guarantee token savings, infer semantic duplicates among arbitrary tasks, or establish production readiness. They do not automatically upgrade the installed desktop app.

## Local validation — 12 October 2026

The full run passed 316 tests. After enabling local network access and updating the missing-verdict expectation, 13 previously failing tests passed. The additional interrupted-parallel-work regression also passed, for 330 distinct passing tests in total. Seven browser-dependent tests remain blocked by macOS Chromium startup (`bootstrap_check_in ... Permission denied (1100)`), not passing. Focused workflow/engine tests, compilation and `git diff --check` passed. No desktop release or installation was performed.
