import pytest
from vittics_builder.agent import RunResult
from vittics_builder.timings import summary, timed_stage


def test_records_success_stopped_and_original_failure(co):
    class Runner:
        db = co.db
        @timed_stage('agent')
        def run(self, agent, instructions, ws, **kw):
            if instructions == 'fail':
                raise ValueError('original failure')
            return RunResult(completed=instructions == 'done')
    runner = Runner()
    for instruction in ('done', 'stop'):
        runner.run({'role': 'backend_engineer'}, instruction, None)
    with pytest.raises(ValueError, match='original failure'):
        runner.run({'role': 'backend_engineer'}, 'fail', None)
    rows = co.db.all('SELECT * FROM stage_timings ORDER BY id')
    assert [r['outcome'] for r in rows] == ['completed', 'stopped', 'error']
    assert all(r['seconds'] >= 0 for r in rows)
    stats = summary(co.db)['stages'][0]
    assert stats['samples'] == 3 and stats['errors'] == 1
    assert stats['p95_seconds'] == max(r['seconds'] for r in rows)


def test_performance_endpoint_requires_auth(co):
    from fastapi.testclient import TestClient
    from vittics_builder.server import create_app
    with TestClient(create_app(co, {'ceo': 'boss', 'cto': 'tech'})) as client:
        assert client.get('/api/performance').status_code == 401
        assert client.get('/api/performance', headers={'X-Token': 'boss'}).json()['stages'] == []


def test_presence_uses_constant_query_count(co, monkeypatch):
    from vittics_builder.telemetry import presence
    original = co.db.all
    calls = []
    def query(sql, *args):
        calls.append(sql)
        return original(sql, *args)
    monkeypatch.setattr(co.db, 'all', query)
    people = presence(co.db)
    assert len(people) == 22
    assert len(calls) == 4


def test_recent_timing_sample_window(co):
    for i in range(1001):
        co.db.run('INSERT INTO stage_timings (stage,seconds,outcome,created_at) VALUES (?,?,?,?)',
                  'checks', i, 'passed', '2026-01-01')
    stats = summary(co.db)['stages'][0]
    assert stats['samples'] == 1000
    assert stats['mean_seconds'] == 500.5
    assert stats['p95_seconds'] == 950
