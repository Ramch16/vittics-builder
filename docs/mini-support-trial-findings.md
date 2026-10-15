# Mini Support Desk trial findings

Source: read-only inspection of project 4 in the local company database on 2026-10-14 (America/New_York). Timestamps below are UTC. No trial was rerun for this analysis.

## Version and timing

The installed application's Info.plist reports **0.24.0**. This was not a trial of v0.25.0 or the PR #7 implementation. Results must not be attributed to those versions.

- First run: October 14, 18:36:25.
- Engine-unavailable pause: 18:37:39; next run: 23:05:43. Gap: **4h 28m 04s**. The stored message is clipped; it establishes engine unavailability, not a precise underlying provider error.
- A human pause was recorded at 23:05:47. Requirements approval became pending at 23:07:59 and was approved October 15, 00:14:17. Gap: **1h 06m 18s**, overlapping the human pause. Do not count those two labels as separate additive delays.
- Architecture approved: 00:15:55. Two implementation tickets ran concurrently.
- Release sign-off pending: 00:34:02; approved: 00:39:19.
- Preview running: 00:39:20. Total elapsed from first run: **6h 02m 55s**.
- Union of recorded agent intervals, including status reporting: **16m 36s**. This is agent activity, not total host test/runtime execution time.

The elapsed time primarily reflects unavailable-engine and decision/pause intervals. It is not six hours of continuous code generation.

## Duplicate work and repair accounting

T-101 was an agent-filed proposal during requirements; T-103 was created from the architecture plan with the same title. Both were executed. v0.25 already keeps unsolicited planning proposals in backlog; the installed v0.24 did not include that fix.

The `attempts` column records review rejections. T-103's value of 2 means the initial candidate and its repair were rejected; it does not prove two repairs. T-101 also restarted following a merge conflict. The old implementation had no persistent count of actual builder starts across the project.

## New controls

- Identical open agent proposals (same project, title, description, role, type and priority) reuse the existing ticket. Different scopes and explicit human-created tickets are preserved. This is exact idempotency, not semantic deduplication.
- `tasks.builder_starts` records builder launch reservations. `projects.repair_starts` records launches after a task's first launch, including conflict-driven rebuilds, and every bug/fix-ticket launch, including newly filed audit repairs. Legacy tasks with recorded rejections are treated as repairs, but historical unrecorded launches cannot be reconstructed.
- Small projects default to **one project-wide repair launch**. Standard projects retain the previous behavior unless `pipeline.max_project_repairs` is configured. Set a nonnegative integer for an explicit cap or `null` for no project-wide cap. Per-ticket review limits continue to apply independently.
- Reservations are durable and transactional across database connections. Review-checkpoint resumes do not consume a repair. Interrupted launches remain charged conservatively because they may already have consumed tokens or changed files.
- Exhaustion stops before another builder call, preserves the task as Todo and reports the limit. It never marks work accepted. A retry/transfer cannot reset the project counter; an explicit configuration increase is required for further repair launches. Counters are lifetime project totals, not reset per release.

These controls do not enforce a total model-token budget or guarantee completion. No installed application or historical project data was modified by implementing them in the source repository.
