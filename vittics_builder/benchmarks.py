"""Read-only, reproducible snapshots of recorded work; never invoke a model.

Completion in the tracker is deliberately not reported as verified acceptance.
Historical usage stores combined input counts, so cache components remain unknown.
"""
from __future__ import annotations

from datetime import datetime, timezone


def instant(value):
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        raise ValueError('Benchmark timestamps must include a timezone.')
    return dt.astimezone(timezone.utc)


def summarize(runs, usage, tasks, cutoff):
    end = instant(cutoff)
    spans = []
    for run in runs:
        start = instant(run['started_at'])
        stop = min(instant(run['ended_at']), end) if run['ended_at'] else end
        if start > end:
            continue
        if stop < start:
            raise ValueError('Run ends before it starts.')
        spans.append((start, stop))
    merged = []
    for start, stop in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(stop, merged[-1][1]))
        else:
            merged.append((start, stop))
    active = sum((b-a).total_seconds() for a,b in merged)
    wall = (max(b for a,b in spans)-min(a for a,b in spans)).total_seconds() if spans else 0
    known_cost = sum(u['cost'] for u in usage if u['priced'])
    unknown = sum(not u['priced'] for u in usage)
    return {
        'run_count': len(runs),
        'unfinished_runs': sum(not r['ended_at'] for r in runs),
        'observed_wall_seconds': wall,
        'active_union_seconds': active,
        'summed_agent_seconds': sum((b-a).total_seconds() for a,b in spans),
        'between_run_seconds': wall-active,
        'recorded_input_tokens': sum(u['input_tokens'] for u in usage),
        'recorded_output_tokens': sum(u['output_tokens'] for u in usage),
        'cache_read_tokens': None, 'cache_write_tokens': None,
        'known_recorded_cost_usd': known_cost,
        'total_recorded_cost_usd': None if unknown else known_cost,
        'unpriced_calls': unknown,
        'done_tasks': sum(t['status'] == 'done' for t in tasks),
        'recorded_rework_attempts': sum(t['attempts'] for t in tasks),
        'recorded_builder_starts': sum(t.get('builder_starts', 0) for t in tasks),
        'verified_accepted_tasks': None,
        'cost_per_verified_accepted_task': None,
        'release_success': None,
    }


def snapshot(db, project_id, cutoff):
    with db.lock:
        return _snapshot(db, project_id, cutoff)


def _snapshot(db, project_id, cutoff):
    """Export metadata only: excludes prompts, tool output, secrets and paths.

    Caller should provide a fixed cutoff for repeatable reports. One SQLite read
    transaction keeps runs and usage consistent while workers are active.
    """
    instant(cutoff)
    db.conn.execute('SAVEPOINT benchmark_snapshot')
    try:
        project = db.one('SELECT id, name, stage, repair_starts FROM projects WHERE id=?', project_id)
        if not project:
            raise ValueError(f'No project {project_id}.')
        runs = db.all('SELECT id, ticket_id, purpose, status, started_at, ended_at FROM runs '
                      'WHERE project_id=? ORDER BY id', project_id)
        usage = db.all('SELECT id, run_id, model, input_tokens, output_tokens, cost, priced, created_at '
                       'FROM usage WHERE project_id=? ORDER BY id', project_id)
        tasks = db.all('SELECT id, status, attempts, builder_starts FROM tasks WHERE project_id=? ORDER BY id', project_id)
        # Compare parsed times, not lexicographic strings with different offsets.
        runs = [r for r in runs if instant(r['started_at']) <= instant(cutoff)]
        usage = [u for u in usage if instant(u['created_at']) <= instant(cutoff)]
        return {'schema_version': 1, 'cutoff': cutoff, 'project': project,
                'summary': summarize(runs, usage, tasks, cutoff),
                'runs': runs, 'usage': usage, 'tasks': tasks,
                'limitations': [
                    'Task status is current snapshot state, not historical state at cutoff.',
                    'Builder/repair start counters begin at migration; earlier launches are not reconstructed.',
                    'Recorded cost may be estimated or subscription-reported; it is not an invoice.',
                    'Cache input components cannot be reconstructed from historical combined input.',
                    'Between-run time is not classified approval or infrastructure waiting time.',
                    'Tracker completion does not establish independent acceptance or release success.']}
    finally:
        db.conn.execute('RELEASE benchmark_snapshot')
