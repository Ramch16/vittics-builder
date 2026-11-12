from concurrent.futures import ThreadPoolExecutor

import pytest

from vittics_builder.company import Company
from vittics_builder.engines import EngineUnavailable
from vittics_builder.llm import MockProvider


def test_run_cap_survives_restart_and_counts_failures(co):
    p = co.pipeline.create_project('Bounded', 'Test')
    agent = co.org.agent('Ram')
    rid = co.runs.start(agent, p['id'], None, 'builder', 'Work', limit=1)
    co.runs.finish(rid, 'failed')
    other = Company(co.s.root, provider=MockProvider())
    with pytest.raises(EngineUnavailable, match='agent-run limit'):
        other.runs.start(agent, p['id'], None, 'reviewer', 'Review', limit=1)
    assert len(co.db.all('SELECT * FROM runs WHERE project_id=?', p['id'])) == 1


def test_parallel_run_reservations_cannot_overspend(co):
    p = co.pipeline.create_project('Bounded', 'Test')
    other = Company(co.s.root, provider=MockProvider())
    agent = co.org.agent('Ram')
    def reserve(runs):
        try:
            runs.start(agent, p['id'], None, 'builder', 'Work', limit=1)
            return True
        except EngineUnavailable:
            return False
    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(reserve, [co.runs, other.runs])) == [False, True]


def test_cap_prevents_provider_and_routing_launch(co, monkeypatch):
    p = co.pipeline.create_project('Bounded', 'Test')
    co.s.raw.setdefault('pipeline', {})['max_project_runs'] = 0
    def forbidden(*args, **kwargs):
        pytest.fail('No model or route should start')
    monkeypatch.setattr(co.runtime, '_run', forbidden)
    monkeypatch.setattr(co.router, 'start', forbidden)
    with pytest.raises(EngineUnavailable, match='agent-run limit'):
        co.runtime.run(co.org.agent('Ram'), 'Work', None, project_id=p['id'])


def test_cancelled_assignment_is_not_left_running(co, monkeypatch):
    def cancel(*args, **kwargs):
        raise KeyboardInterrupt()
    monkeypatch.setattr(co.runtime, '_run', cancel)
    with pytest.raises(KeyboardInterrupt):
        co.runtime.run(co.org.agent('Ram'), 'Work', None)
    row = co.db.one('SELECT * FROM runs ORDER BY id DESC LIMIT 1')
    assert row['status'] == 'stopped'
    assert row['ended_at']


@pytest.mark.parametrize('limit', [-1, True, '5'])
def test_invalid_cap_rejected(co, limit):
    with pytest.raises(ValueError, match='nonnegative integer'):
        co.runs.start(co.org.agent('Ram'), None, None, 'chat', 'Hi', limit=limit)


@pytest.mark.parametrize('size, limit', [('small', 40), ('standard', 80)])
def test_default_allowance_is_enforced_before_runtime(co, monkeypatch, size, limit):
    p = co.pipeline.create_project('Bounded', 'Test', size=size)
    agent = co.org.agent('Ram')
    for _ in range(limit):
        rid = co.runs.start(agent, p['id'], None, 'reviewer', 'Review')
        co.runs.finish(rid, 'done')
    def forbidden(*args, **kwargs):
        pytest.fail('No provider should start')
    monkeypatch.setattr(co.runtime, '_run', forbidden)
    with pytest.raises(EngineUnavailable, match=f'{limit}/{limit}'):
        co.runtime.run(agent, 'Work', None, project_id=p['id'])


def test_explicit_null_allows_assignment(co, monkeypatch):
    from vittics_builder.agent import RunResult
    p = co.pipeline.create_project('Bounded', 'Test')
    co.s.raw.setdefault('pipeline', {})['max_project_runs'] = None
    monkeypatch.setattr(co.runtime, '_run', lambda *a, **k: RunResult(completed=True))
    assert co.runtime.run(co.org.agent('Ram'), 'Work', None, project_id=p['id']).completed


def test_project_limit_pause_does_not_suggest_engine_retry(co):
    from vittics_builder.pipeline import PipelineError
    p = co.pipeline.create_project('Bounded', 'Test')
    co.s.raw.setdefault('pipeline', {})['max_project_runs'] = 0
    with pytest.raises(PipelineError, match='retrying alone will not reset'):
        co.pipeline.advance(p['id'])
    assert not co.db.all('SELECT * FROM runs WHERE project_id=?', p['id'])
    assert not co.pipeline.running(p['id'])


def test_nested_project_limit_does_not_rest_provider_or_failover(co, monkeypatch):
    from vittics_builder.engines import ProjectRunLimit
    class Failover:
        enabled = True
        def resting(self, model):
            return None
        def rest(self, *args):
            pytest.fail('Project limits must not mark a provider unavailable')
    co.runtime.failover = Failover()
    def nested_limit(*args, **kwargs):
        raise ProjectRunLimit('Project agent-run limit reached')
    monkeypatch.setattr(co.runtime, '_run', nested_limit)
    with pytest.raises(ProjectRunLimit):
        co.runtime.run(co.org.agent('Ram'), 'Delegate', None)
    assert co.db.one('SELECT status FROM runs ORDER BY id DESC LIMIT 1')['status'] == 'failed'
