import copy
import json

import pytest

from vittics_builder.comparison import compare


def trial(identifier='a', **changes):
    return dict(id=identifier, system='vittics', version='test', workload='crud',
                **{field: 'a'*64 for field in ('brief_sha256', 'starter_sha256', 'acceptance_sha256',
                   'environment_sha256', 'models_sha256', 'policy_sha256')},
                started_at='2026-01-01T00:00:00+00:00', stopped_at='2026-01-01T00:10:00+00:00',
                status='accepted', independent_acceptance=True, evidence='retained-report.json',
                cost_usd=2, cost_basis='estimated', defects=0) | changes


def report(*trials):
    return compare({'schema_version': 1, 'trials': list(trials)})


def test_failures_and_timeouts_count_toward_delivery_cost():
    s = report(trial(), trial('b', status='failed', cost_usd=3, defects=2),
               trial('c', status='incomplete', cost_usd=5))['cohorts'][0]['systems'][0]
    assert s['cost_per_accepted_delivery_usd'] == 10
    assert s['acceptance_rate'] == 1/3
    assert s['incomplete'] == 1
    assert s['defects'] == 2
    assert s['wall_seconds']['median'] == 600


def test_unknown_cost_and_no_acceptance_are_not_free():
    s = report(trial(cost_usd=None, cost_basis='unknown'))['cohorts'][0]['systems'][0]
    assert s['total_cost_usd'] is None
    assert s['cost_per_accepted_delivery_usd'] is None
    s = report(trial(status='failed'))['cohorts'][0]['systems'][0]
    assert s['cost_per_accepted_delivery_usd'] is None


def test_only_matching_inputs_share_a_cohort():
    result = report(trial(), trial('b', system='paperclip'),
                    trial('c', system='paperclip', models_sha256='b'*64))
    assert len(result['cohorts']) == 2
    assert len(result['cohorts'][0]['systems']) == 2
    assert 'Unmatched cohort' in result['cohorts'][1]['warnings'][0]


@pytest.mark.parametrize('changes', [
    {'cost_usd': -1}, {'cost_usd': float('nan')}, {'cost_usd': True},
    {'cost_usd': None}, {'defects': -1}, {'defects': True},
    {'independent_acceptance': False}, {'evidence': ''}, {'models_sha256': 'unfrozen'},
    {'started_at': '2026-01-01T00:00:00'}, {'stopped_at': '2025-01-01T00:00:00+00:00'},
    {'started_at': None}, {'stopped_at': None},
])
def test_invalid_trials_fail(changes):
    with pytest.raises(ValueError):
        report(trial(**changes))


def test_duplicates_rejected_and_input_not_mutated():
    with pytest.raises(ValueError, match='Duplicate'):
        report(trial(), trial())
    t = trial()
    before = copy.deepcopy(t)
    assert report(t) == report(t)
    assert t == before


def test_cli_needs_no_company_and_never_executes_evidence(tmp_path, capsys):
    from vittics_builder.cli import main
    path = tmp_path / 'trials.json'
    path.write_text(json.dumps({'schema_version': 1, 'trials': [trial(evidence='not-a-command')]}))
    assert main(['--home', str(tmp_path / 'absent'), 'benchmark-compare', str(path)]) == 0
    assert json.loads(capsys.readouterr().out)['cohorts'][0]['systems'][0]['accepted'] == 1
