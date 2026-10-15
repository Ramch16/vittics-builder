from concurrent.futures import ThreadPoolExecutor

import pytest

from vittics_builder.company import Company
from vittics_builder.llm import MockProvider
from vittics_builder.pipeline import PipelineError


def setup(co):
    p = co.pipeline.create_project('Bounded trial', 'Small project', size='small')
    tasks = [co.tickets.create(p['id'], f'Task {i}', 'Implement', 'Lucky', status='todo',
                               role='backend_engineer') for i in range(2)]
    return p, tasks


def test_repair_budget_is_shared_and_survives_reopen(co):
    p, tasks = setup(co)
    for t in tasks:
        co.pipeline._reserve_builder_start(p['id'], t['id'])
    co.pipeline._reserve_builder_start(p['id'], tasks[0]['id'])
    reopened = Company(co.s.root, provider=MockProvider())
    with pytest.raises(PipelineError, match='repair limit'):
        reopened.pipeline._reserve_builder_start(p['id'], tasks[1]['id'])
    assert co.pipeline.project(p['id'])['repair_starts'] == 1
    assert co.db.one('SELECT builder_starts FROM tasks WHERE id=?', tasks[1]['id'])['builder_starts'] == 1


def test_parallel_repairs_cannot_overspend(co):
    p, tasks = setup(co)
    for t in tasks:
        co.pipeline._reserve_builder_start(p['id'], t['id'])
    other = Company(co.s.root, provider=MockProvider())
    def reserve(pair):
        pipeline, task = pair
        try:
            pipeline._reserve_builder_start(p['id'], task['id'])
            return True
        except PipelineError:
            return False
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(reserve, [(co.pipeline, tasks[0]), (other.pipeline, tasks[1])]))
    assert sorted(results) == [False, True]


def test_new_fix_tickets_share_the_same_budget(co):
    p, _ = setup(co)
    first = co.pipeline._fix_task(p['id'], 'Fix test', 'Broken')
    second = co.pipeline._fix_task(p['id'], 'Fix audit', 'Broken too')
    co.pipeline._reserve_builder_start(p['id'], first)
    with pytest.raises(PipelineError, match='repair limit'):
        co.pipeline._reserve_builder_start(p['id'], second)


def test_exhausted_limit_does_not_launch_builder_or_complete_task(co, monkeypatch):
    p, tasks = setup(co)
    co.s.raw.setdefault('pipeline', {})['max_project_repairs'] = 0
    co.pipeline._reserve_builder_start(p['id'], tasks[0]['id'])
    def forbidden(*args, **kwargs):
        pytest.fail('Builder must not launch')
    monkeypatch.setattr(co.runtime, 'run', forbidden)
    with pytest.raises(PipelineError, match='repair limit'):
        co.pipeline._run_task(p, tasks[0], co.pipeline.workspace(p))
    assert co.db.one('SELECT status FROM tasks WHERE id=?', tasks[0]['id'])['status'] == 'todo'


def test_identical_agent_proposal_is_reused_but_human_and_different_scope_are_not(co):
    p, _ = setup(co)
    args = dict(project_id=p['id'], title='Implement', description='Scope A', by='Ram',
                role='backend_engineer', origin='agent')
    first = co.tickets.create(**args)
    assert co.tickets.create(**args)['id'] == first['id']
    assert co.tickets.create(**{**args, 'description': 'Scope B'})['id'] != first['id']
    assert co.tickets.create(**{**args, 'origin': 'human'})['id'] != first['id']


def test_concurrent_agent_proposals_across_connections_are_idempotent(co):
    p, _ = setup(co)
    other = Company(co.s.root, provider=MockProvider())
    def propose(tickets):
        return tickets.create(p['id'], 'Same proposal', 'Same scope', 'Ram',
                              role='backend_engineer', origin='agent')['id']
    with ThreadPoolExecutor(2) as pool:
        ids = list(pool.map(propose, [co.tickets, other.tickets]))
    assert ids[0] == ids[1]


@pytest.mark.parametrize('limit', [-1, True, '1'])
def test_invalid_limits_fail_before_launch(co, limit):
    p, tasks = setup(co)
    co.s.raw.setdefault('pipeline', {})['max_project_repairs'] = limit
    with pytest.raises(PipelineError, match='nonnegative'):
        co.pipeline._reserve_builder_start(p['id'], tasks[0]['id'])
