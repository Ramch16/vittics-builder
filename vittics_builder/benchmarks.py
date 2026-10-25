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


# ---- run records (docs/research/run-record.schema.json; DRAFT, not approved for experiments) ----------------
SCHEMA_PATH = 'docs/research/run-record.schema.json'
_TYPES = {'object': dict, 'array': list, 'string': str, 'boolean': bool, 'null': type(None)}


def _is(value, kind):
    if kind == 'integer':
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == 'number':
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, _TYPES[kind])


def validate_record(record, schema, path='$'):
    """Errors (a list of strings, empty when valid) for `record` against the keywords the run-record schema
    uses: type, required, properties, additionalProperties, items, enum, const, minimum, minLength, pattern
    and format (date-time, date). Not a general JSON Schema validator; anything else raises."""
    import re as _re
    known = {'$schema', '$id', 'title', 'description', 'type', 'required', 'properties', 'additionalProperties',
             'items', 'enum', 'const', 'minimum', 'minLength', 'pattern', 'format'}
    if set(schema) - known:
        raise ValueError(f'{path}: unsupported schema keywords {sorted(set(schema) - known)}')
    errors = []
    if 'const' in schema and record != schema['const']:
        return [f'{path}: must be {schema["const"]!r}']
    if 'enum' in schema and record not in schema['enum']:
        return [f'{path}: {record!r} is not one of {schema["enum"]}']
    kinds = schema.get('type')
    if kinds is not None:
        kinds = [kinds] if isinstance(kinds, str) else kinds
        if not any(_is(record, k) for k in kinds):
            return [f'{path}: expected {"/".join(kinds)}, got {type(record).__name__}']
    if record is None:
        return errors
    if isinstance(record, str):
        if len(record) < schema.get('minLength', 0):
            errors.append(f'{path}: too short')
        if 'pattern' in schema and not _re.search(schema['pattern'], record):
            errors.append(f'{path}: does not match {schema["pattern"]}')
        fmt = schema.get('format')
        try:
            if fmt == 'date-time':
                instant(record.replace('Z', '+00:00'))
            elif fmt == 'date':
                datetime.strptime(record, '%Y-%m-%d')
        except ValueError:
            errors.append(f'{path}: not a valid {fmt} with timezone')
    if 'minimum' in schema and _is(record, 'number') and record < schema['minimum']:
        errors.append(f'{path}: below {schema["minimum"]}')
    if isinstance(record, dict):
        for key in schema.get('required', []):
            if key not in record:
                errors.append(f'{path}: missing {key}')
        props = schema.get('properties', {})
        for key, value in record.items():
            if key in props:
                errors += validate_record(value, props[key], f'{path}.{key}')
            elif schema.get('additionalProperties') is False:
                errors.append(f'{path}: unexpected field {key}')
    if isinstance(record, list) and 'items' in schema:
        for i, item in enumerate(record):
            errors += validate_record(item, schema['items'], f'{path}[{i}]')
    return errors


def _total(values):
    """Sum, or None if any value is unknown: unknown is never treated as zero."""
    values = list(values)
    return None if any(v is None for v in values) else sum(values)


def summarize_records(records):
    """Per-condition and task-paired summaries of validated run records (benchmark-protocol-draft.md §8–9).
    Failed and incomplete runs count everywhere, including cost. Cost per accepted run is None when no run was
    accepted or any cost is unknown. The unit of comparison is the task: repeats are averaged within a task."""
    data_kinds = sorted({r['data_kind'] for r in records})
    by_condition = {}
    for condition in sorted({r['condition'] for r in records}):
        runs = [r for r in records if r['condition'] == condition]
        accepted = sum(r['terminal_status'] == 'accepted' for r in runs)
        reached = [r for r in runs if r['acceptance']['release_outcome'] in ('released', 'release_blocked')]
        cost = _total(r['cost']['amount'] for r in runs)
        by_condition[condition] = {
            'runs': len(runs), 'tasks': len({r['task_id'] for r in runs}),
            'accepted_runs': accepted, 'acceptance_rate': accepted / len(runs),
            'release_reliability': (sum(r['acceptance']['release_outcome'] == 'released' for r in reached) / len(reached)
                                    if reached else None),
            'incomplete_runs': sum(r['ended_at'] is None for r in runs),
            'terminal_statuses': {s: sum(r['terminal_status'] == s for r in runs)
                                  for s in sorted({r['terminal_status'] for r in runs})},
            'total_cost': cost, 'currencies': sorted({r['cost']['currency'] for r in runs if r['cost']['currency']}),
            'unknown_cost_runs': sum(r['cost']['amount'] is None for r in runs),
            'cost_per_accepted_run': cost / accepted if cost is not None and accepted else None,
            'human_minutes': _total(i['minutes'] for r in runs for i in r['human_interventions']),
            'input_tokens': _total(r['usage']['input_tokens'] for r in runs),
            'output_tokens': _total(r['usage']['output_tokens'] for r in runs),
        }
    paired = []
    for task in sorted({r['task_id'] for r in records}):
        rates = {}
        for condition in ('multi_agent', 'single_agent'):
            runs = [r for r in records if r['task_id'] == task and r['condition'] == condition]
            rates[condition] = (sum(r['terminal_status'] == 'accepted' for r in runs) / len(runs), len(runs)) if runs else None
        if rates['multi_agent'] and rates['single_agent']:
            paired.append({'task_id': task, 'multi_agent_rate': rates['multi_agent'][0],
                           'single_agent_rate': rates['single_agent'][0],
                           'repeats': {'multi_agent': rates['multi_agent'][1], 'single_agent': rates['single_agent'][1]},
                           'difference': rates['multi_agent'][0] - rates['single_agent'][0]})
    diffs = sorted(p['difference'] for p in paired)
    mid = len(diffs) // 2
    return {'schema_version': 1, 'data_kinds': data_kinds, 'by_condition': by_condition, 'task_paired': paired,
            'paired_summary': {'tasks': len(diffs),
                               'median_difference': (diffs[mid] if len(diffs) % 2 else (diffs[mid - 1] + diffs[mid]) / 2)
                               if diffs else None,
                               'min_difference': diffs[0] if diffs else None,
                               'max_difference': diffs[-1] if diffs else None},
            'limitations': ['Exploratory: no significance test; repeats are clustered by task.',
                            'Synthetic or mock records say nothing about real performance.'
                            if any(k != 'observed' for k in data_kinds) else 'Pilot sample; see the protocol.']}
