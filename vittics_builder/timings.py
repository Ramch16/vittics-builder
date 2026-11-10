"""Bounded wall-clock samples for finding slow stages; never acceptance evidence."""
from functools import wraps
import logging
import sqlite3
import time

from .db import now


def timed_stage(stage):
    def decorate(fn):
        @wraps(fn)
        def measured(self, *args, **kwargs):
            started = time.perf_counter()
            subject = args[0] if args else kwargs['agent' if stage == 'agent' else 'p']
            project_id = kwargs.get('project_id') if stage == 'agent' else subject['id']
            label = f"agent:{subject['role']}" if stage == 'agent' else stage
            outcome = 'error'
            try:
                result = fn(self, *args, **kwargs)
                if stage == 'agent':
                    outcome = 'completed' if result.completed else 'stopped'
                else:
                    outcome = 'passed' if result.get('passed') else 'failed'
                return result
            finally:
                elapsed = max(0, time.perf_counter() - started)
                try:
                    with self.db.lock:
                        row_id = self.db.run(
                            'INSERT INTO stage_timings (project_id,stage,seconds,outcome,created_at) VALUES (?,?,?,?,?)',
                            project_id, label, elapsed, outcome, now())
                        self.db.run('DELETE FROM stage_timings WHERE id<=?', row_id - 10000)
                except sqlite3.Error:
                    # Diagnostics must not interrupt delivery or replace its original exception.
                    logging.getLogger(__name__).exception('Could not record stage timing')
        return measured
    return decorate


def summary(db):
    rows = db.all('SELECT stage,seconds,outcome FROM (SELECT * FROM stage_timings ORDER BY id DESC LIMIT 1000)')
    groups = {}
    for row in rows:
        group = groups.setdefault(row['stage'], {'stage': row['stage'], 'samples': 0, 'errors': 0, 'total_seconds': 0.0, 'values': []})
        group['samples'] += 1
        group['errors'] += row['outcome'] == 'error'
        group['total_seconds'] += row['seconds']
        group['values'].append(row['seconds'])
    for group in groups.values():
        values = sorted(group.pop('values'))
        group['mean_seconds'] = group['total_seconds'] / group['samples']
        group['p95_seconds'] = values[max(0, (95 * len(values) + 99) // 100 - 1)]
    return {'sample_limit': 1000, 'stages': sorted(groups.values(), key=lambda r: -r['total_seconds']),
            'note': 'Recent wall-clock durations, including failed attempts. Parallel stages overlap; totals are not project elapsed time.'}
