import pytest

from vittics_builder.review_policy import review_level


@pytest.mark.parametrize('paths,expected', [
    (['docs/guide.md', 'README.md'], 'light'),
    (['docs/example.py'], 'standard'),
    (['docs/demo.html'], 'standard'),
    (['docs/guide.md', 'src/app.py'], 'standard'),
    (['requirements.txt'], 'standard'),
    (['docs/authentication.md'], 'thorough'),
    (['db/migrations/001.sql'], 'thorough'),
    (['.github/workflows/test.yml'], 'thorough'),
    (['product.json'], 'thorough'),
    ([], 'standard'),
])
def test_conservative_paths(paths, expected):
    assert review_level({}, paths)[0] == expected


def test_task_risk_and_rework_cannot_lower_review():
    assert review_level({'title': 'Fix permission bypass'}, ['docs/guide.md'])[0] == 'thorough'
    assert review_level({'attempts': 1}, ['docs/guide.md'])[0] == 'standard'


def test_adaptive_small_projects_keep_sensitive_review(co):
    co.s.review_mode = 'adaptive'
    p = co.pipeline.create_project('Small', 'A small change', size='small')
    roles = co.pipeline._checkers(p['id'], task={}, paths=['src/auth.py'])
    assert {r['id'] for r in roles} == {'code_reviewer', 'security_engineer', 'qa_engineer'}
    assert len(co.pipeline._checkers(p['id'], paths=['docs/guide.md'])) == 1
    assert len(co.pipeline._checkers(p['id'], paths=['app.py'])) == 2


def test_sensitive_paths_survive_interrupted_review(co, monkeypatch):
    import json
    from vittics_builder.agent import RunResult
    from vittics_builder.engines import EngineUnavailable

    co.s.review_mode = 'adaptive'
    p = co.pipeline.create_project('Resume', 'A library', size='small')
    task = co.tickets.create(p['id'], 'Core', 'Build core', 'Lucky', status='todo', role='backend_engineer')
    ws = co.pipeline.workspace(p)
    original = co.runtime.run
    reviewers = []
    builds = []
    def run(agent, instructions, workspace, **kw):
        if (kw.get('meta') or {}).get('author'):
            reviewers.append(agent['role'])
            if len(reviewers) == 1:
                raise EngineUnavailable('At capacity')
            return original(agent, instructions, workspace, **kw)
        builds.append(agent['id'])
        workspace.write_file('src/auth.py', '# sensitive change\n')
        workspace.commit('Builder may create its own commits')
        return RunResult(completed=True, text='Implemented')
    monkeypatch.setattr(co.runtime, 'run', run)
    with pytest.raises(EngineUnavailable):
        co.pipeline._run_task(p, task, ws)
    saved = co.db.one('SELECT result FROM tasks WHERE id=?', task['id'])
    assert 'src/auth.py' in json.loads(saved['result'])['review_paths']
    assert co.pipeline._run_task(p, task, ws)
    assert len(builds) == 1
    assert 'security_engineer' in reviewers
