import copy
import importlib.util
import json
from pathlib import Path

import pytest

from vittics_builder.benchmarks import SCHEMA_PATH, snapshot, summarize, summarize_records, validate_record


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


# ---- run records and the synthetic dry run (docs/research/; DRAFT protocol) ------------------------------------
REPO = Path(__file__).resolve().parent.parent


def _dry_run():
    spec = importlib.util.spec_from_file_location('synthetic_dry_run', REPO / 'scripts' / 'synthetic_dry_run.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _schema():
    return json.loads((REPO / SCHEMA_PATH).read_text(encoding='utf-8'))


def test_synthetic_records_are_valid_and_labelled_synthetic():
    records = _dry_run().synthetic_records()
    assert len(records) == 12
    assert all(validate_record(r, _schema()) == [] for r in records)
    assert {r['data_kind'] for r in records} == {'synthetic'}


@pytest.mark.parametrize('field,value,message', [
    (('cost', 'amount'), -1, 'below 0'),
    (('terminal_status',), 'done', 'is not one of'),
    (('started_at',), '2026-01-01T00:00:00', 'not a valid date-time'),    # no timezone
    (('usage', 'input_tokens'), '10', 'expected integer/null'),
    (('data_kind',), 'real', 'is not one of'),
    (('source', 'harness_commit'), 'abc', 'does not match'),
])
def test_invalid_records_are_reported(field, value, message):
    record = copy.deepcopy(_dry_run().synthetic_records()[0])
    target = record
    for key in field[:-1]:
        target = target[key]
    target[field[-1]] = value
    assert any(message in e for e in validate_record(record, _schema()))


def test_missing_and_extra_fields_are_reported():
    record = copy.deepcopy(_dry_run().synthetic_records()[0])
    del record['cost']
    record['score'] = 99
    errors = validate_record(record, _schema())
    assert '$: missing cost' in errors and '$: unexpected field score' in errors


def test_dry_run_summary_propagates_unknowns_and_zero_acceptance():
    summary = summarize_records(_dry_run().synthetic_records())
    ma, sa = summary['by_condition']['multi_agent'], summary['by_condition']['single_agent']
    assert (ma['accepted_runs'], sa['accepted_runs']) == (4, 0)
    assert ma['total_cost'] is None and ma['unknown_cost_runs'] == 1       # one incomplete run, cost unknown
    assert ma['cost_per_accepted_run'] is None                            # unknown never becomes zero
    assert ma['input_tokens'] is None and ma['incomplete_runs'] == 1
    assert sa['total_cost'] == 3.0                                        # failed and timed-out runs still cost
    assert sa['cost_per_accepted_run'] is None                            # zero accepted: undefined
    assert sa['terminal_statuses'] == {'failed': 1, 'provider_unavailable': 1, 'rejected': 3, 'timeout': 1}
    assert sa['release_reliability'] == 0.0 and ma['release_reliability'] == 1.0
    assert [p['difference'] for p in summary['task_paired']] == [1.0, 0.5, 0.5]
    assert summary['paired_summary'] == {'tasks': 3, 'median_difference': 0.5, 'min_difference': 0.5,
                                         'max_difference': 1.0}
    assert summary['data_kinds'] == ['synthetic']


def test_cost_per_accepted_run_when_everything_is_known():
    records = [r for r in _dry_run().synthetic_records() if r['condition'] == 'multi_agent' and r['cost']['amount'] is not None]
    s = summarize_records(records)['by_condition']['multi_agent']
    assert s['total_cost'] == 2.5 and s['accepted_runs'] == 4 and s['cost_per_accepted_run'] == 0.625


def test_dry_run_script_is_deterministic(tmp_path):
    module = _dry_run()
    assert module.main(['--out', str(tmp_path / 'a')]) == 0 and module.main(['--out', str(tmp_path / 'b')]) == 0
    for name in ('records.jsonl', 'validation.json', 'summary.json'):
        assert (tmp_path / 'a' / name).read_bytes() == (tmp_path / 'b' / name).read_bytes()
