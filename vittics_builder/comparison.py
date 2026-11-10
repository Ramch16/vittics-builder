"""Offline summaries of externally verified trials. Never executes submitted commands."""
from __future__ import annotations

from collections import defaultdict
import math
from statistics import median

from .benchmarks import instant


def _number(value, field):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError(f'{field} must be a finite nonnegative number.')
    return value


def compare(document):
    """Compare matched trials; failures and incomplete runs remain in denominators.

    Fingerprints identify frozen inputs, not the system/version under test.
    They are operator attestations; this report does not authenticate evidence.
    """
    if not isinstance(document, dict) or document.get('schema_version') != 1:
        raise ValueError('Comparison input needs schema_version 1.')
    trials = document.get('trials')
    if not isinstance(trials, list) or not trials:
        raise ValueError('Comparison input needs a nonempty trials list.')
    groups, seen = defaultdict(list), set()
    match_fields = ('workload', 'brief_sha256', 'starter_sha256', 'acceptance_sha256',
                    'environment_sha256', 'models_sha256', 'policy_sha256')
    for trial in trials:
        if not isinstance(trial, dict):
            raise ValueError('Each trial must be an object.')
        for field in ('id', 'system', 'version', *match_fields, 'evidence', 'started_at', 'stopped_at'):
            if not isinstance(trial.get(field), str) or not trial[field].strip():
                raise ValueError(f'Trial needs nonempty {field}.')
        for field in match_fields[1:]:
            value = trial[field]
            if len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
                raise ValueError(f'{field} must be a lowercase SHA-256 digest.')
        if trial['id'] in seen:
            raise ValueError('Duplicate trial id.')
        seen.add(trial['id'])
        if trial.get('status') not in ('accepted', 'failed', 'incomplete'):
            raise ValueError('Trial status must be accepted, failed or incomplete.')
        if trial.get('independent_acceptance') is not True:
            raise ValueError('Trials require independent acceptance evaluation, including failures.')
        start, stop = instant(trial['started_at']), instant(trial['stopped_at'])
        if stop < start:
            raise ValueError('Trial stops before it starts.')
        cost = trial.get('cost_usd')
        if cost is not None:
            _number(cost, 'cost_usd')
        if trial.get('cost_basis') not in ('billed', 'estimated', 'unknown'):
            raise ValueError('cost_basis must be billed, estimated or unknown.')
        if (cost is None) != (trial['cost_basis'] == 'unknown'):
            raise ValueError('Unknown cost must be null; known cost needs a known basis.')
        defects = trial.get('defects')
        if type(defects) is not int or defects < 0:
            raise ValueError('defects must be a nonnegative integer.')
        key = tuple(trial[f] for f in match_fields)
        groups[key].append({**trial, 'wall_seconds': (stop-start).total_seconds()})

    reports = []
    for key, members in sorted(groups.items()):
        systems = defaultdict(list)
        for t in members:
            systems[(t['system'], t['version'])].append(t)
        summaries = []
        for (system, version), rows in sorted(systems.items()):
            accepted = sum(r['status'] == 'accepted' for r in rows)
            known = sum(r['cost_usd'] for r in rows if r['cost_usd'] is not None)
            unknown = sum(r['cost_usd'] is None for r in rows)
            wall = [r['wall_seconds'] for r in rows]
            summaries.append({
                'system': system, 'version': version, 'trials': len(rows),
                'accepted': accepted, 'acceptance_rate': accepted / len(rows),
                'failed': sum(r['status'] == 'failed' for r in rows),
                'incomplete': sum(r['status'] == 'incomplete' for r in rows),
                'defects': sum(r['defects'] for r in rows),
                'wall_seconds': {'median': median(wall), 'min': min(wall), 'max': max(wall)},
                'known_cost_usd': known, 'unknown_cost_trials': unknown,
                'total_cost_usd': None if unknown else known,
                'cost_per_accepted_delivery_usd': known / accepted if accepted and not unknown else None,
                'cost_bases': sorted({r['cost_basis'] for r in rows}),
                'trial_ids': sorted(r['id'] for r in rows),
            })
        warnings = []
        if len(summaries) < 2:
            warnings.append('Unmatched cohort: fewer than two system/version entries share these inputs.')
        if any(s['trials'] < 3 for s in summaries):
            warnings.append('Fewer than three trials per system; collect more independent trials.')
        if len({s['trials'] for s in summaries}) > 1:
            warnings.append('Trial counts differ; investigate sampling bias before comparing.')
        reports.append({'inputs': dict(zip(match_fields, key)), 'systems': summaries, 'warnings': warnings})
    return {'schema_version': 1, 'cohorts': reports, 'limitations': [
        'Input fingerprints and independent acceptance are supplied by the operator, not authenticated here.',
        'Wall time includes approvals, outages and incomplete trials up to the declared stop.',
        'Failed and incomplete trial costs are included in cost per accepted delivery.',
        'Estimated and billed costs are labeled separately; subscriptions and infrastructure require explicit accounting.',
        'Descriptive results do not establish statistical superiority or equivalent production security.',
    ]}
