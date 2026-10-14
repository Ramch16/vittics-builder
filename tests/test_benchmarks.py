import json

import pytest

from vittics_builder.benchmarks import summarize, snapshot


def run(start, end):
    return {'started_at': f'2026-01-01T00:{start}:00+00:00',
            'ended_at': f'2026-01-01T00:{end}:00+00:00' if end else None}


def test_overlap_and_interrupted_run():
    s = summarize([run('00','10'), run('05','15'), run('20',None)], [], [],
                  '2026-01-01T00:25:00+00:00')
    assert s['active_union_seconds'] == 1200
    assert s['summed_agent_seconds'] == 1500
    assert s['observed_wall_seconds'] == 1500
    assert s['between_run_seconds'] == 300
    assert s['unfinished_runs'] == 1


def test_unknown_cost_and_done_do_not_claim_acceptance():
    s = summarize([], [{'input_tokens': 10, 'output_tokens': 5, 'cost': 0, 'priced': 0},
                       {'input_tokens': 20, 'output_tokens': 8, 'cost': 2, 'priced': 1}],
                  [{'status': 'done', 'attempts': 3}], '2026-01-01T00:00:00+00:00')
    assert s['total_recorded_cost_usd'] is None
    assert s['known_recorded_cost_usd'] == 2
    assert s['recorded_input_tokens'] == 30
    assert s['done_tasks'] == 1
    assert s['verified_accepted_tasks'] is None
    assert s['cache_read_tokens'] is None
    assert s['cost_per_verified_accepted_task'] is None


def test_invalid_timestamps():
    with pytest.raises(ValueError):
        summarize([run('10','05')], [], [], '2026-01-01T00:25:00+00:00')
    with pytest.raises(ValueError):
        summarize([], [], [], '2026-01-01T00:25:00')


def test_export_deterministic_and_no_prompts(co):
    project = co.pipeline.create_project('Benchmark', 'Private brief')
    pid = project['id'] if isinstance(project, dict) else project
    a = snapshot(co.db, pid, '2099-01-01T00:00:00+00:00')
    assert a == snapshot(co.db, pid, '2099-01-01T00:00:00+00:00')
    assert 'Private brief' not in json.dumps(a)
    assert a['summary']['run_count'] == 0


def test_cli_exports_metrics(co, capsys):
    from vittics_builder.cli import main
    p = co.pipeline.create_project('CLI metrics', 'Private brief')
    assert main(['--home', str(co.s.root), 'benchmark', str(p['id']),
                 '--cutoff', '2099-01-01T00:00:00+00:00']) == 0
    assert json.loads(capsys.readouterr().out)['schema_version'] == 1
