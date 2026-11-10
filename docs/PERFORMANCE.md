# Finding and reducing delays

Operations → Stage timings shows average and 95th-percentile wall-clock duration by agent role and
acceptance checks, ordered by total time. Samples include errors and incomplete runs. The authenticated
`GET /api/performance` endpoint exposes the same data. The latest 1,000 completed samples contribute to
the summary; storage retains at most 10,000 samples. Running stages appear once they finish. These are
assignment durations (including tools and failover), not isolated model response times. Parallel work
overlaps, so adding durations does not give project elapsed time. No prompts or credentials are saved
in these samples.

New companies use conservative adaptive review. Existing companies can set this in their own org.yaml:

```yaml
pipeline:
  review_mode: adaptive
  max_parallel: 3
```

Merge those keys into the existing pipeline mapping. Plain documentation gets one reviewer; source
and unknown changes retain code review and QA; sensitive changes get thorough review. Release
verification and existing audit gates still run. Compared with the legacy small-project light policy,
adaptive adds QA for source changes; it reduces review work for plain documentation in standard
projects, not for every workload. Independent tickets already execute concurrently in isolated Git
worktrees. Increasing max_parallel can increase provider throttling, resource contention and costs;
compare timings and reviewed success rates before changing it.

The dashboard makes no automatic state requests while hidden, resumes when visible and waits for a
refresh to finish before polling again. Explicit actions still obtain fresh state. Agent presence uses
four database queries instead of one plus three per agent (67 queries for the default 22-agent team).

Review-only resumptions already reuse unchanged builder work. This change does not cache acceptance
success across runs: databases, services and environment state can change even with identical source.
Final verification continues to execute on the current candidate.

Model routing already supports rules by role, purpose or kind under `routing.rules`. Use models you
have configured and benchmarked for that work; a faster model that repeatedly fails review can be
slower overall. This change preserves your models, budgets and CEO/CTO approval choices. Use the
project's manual approval toggles to remove routine approval waits when you want automation;
exceptions still require human decisions.

Validation commands:

```sh
python -m pytest -q
node --test tests/dashboard_polling.cjs
```

A synthetic local comparison of presence lookup used the same SQLite database with 22 agents and
5,000 recent events, the previous main implementation and this implementation, and 50 calls each.
Median time was 5.468 ms before and 0.766 ms after; returned results were identical. Both used the
same indexes. This isolates the batched lookup and is not an application build-speed benchmark.
