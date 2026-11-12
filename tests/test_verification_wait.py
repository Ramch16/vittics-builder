import pytest
from fastapi.testclient import TestClient
from vittics_builder.agent import RunResult
from vittics_builder.pipeline import PipelineError
from vittics_builder.server import create_app
from test_validation import start_build
from test_pipeline import decide_next


def test_verification_only_release_waits_without_repairs(co, monkeypatch):
    original = co.runtime.run
    def run(agent, *args, **kwargs):
        if (kwargs.get('meta') or {}).get('purpose') == 'integration':
            return RunResult(completed=True, review={'score': 85, 'verdict': 'request_changes',
                'blocker_type': 'verification', 'notes': 'Use VoiceOver on the current candidate and record actual announcements.',
                'acceptance': [{'criterion': 'Screen reader', 'status': 'unverified', 'evidence': 'No AT available'}]})
        return original(agent, *args, **kwargs)
    monkeypatch.setattr(co.runtime, 'run', run)
    p = start_build(co)
    result = decide_next(co, 'cto')
    assert result['stage'] == 'release_blocked'
    assert not co.db.one("SELECT id FROM tasks WHERE project_id=? AND key LIKE 'verify-%'", p['id'])
    pending = next(a for a in co.pipeline.inbox('cto') if a['kind'] == 'release_blocked')
    count = co.db.one('SELECT count(*) AS n FROM tasks')['n']
    with pytest.raises(PipelineError, match='cannot be approved'):
        co.pipeline.decide(pending['id'], 'cto', 'approved')
    co.pipeline.decide(pending['id'], 'cto', 'rejected', 'Human verification is unavailable')
    assert co.pipeline.advance(p['id'])['stage'] == 'release_blocked'
    assert co.db.one('SELECT count(*) AS n FROM tasks')['n'] == count
    pending = next(a for a in co.pipeline.inbox('cto') if a['kind'] == 'release_blocked')
    monkeypatch.setattr(co.runtime, 'run', original)
    co.pipeline.decide(pending['id'], 'cto', 'rejected', 'Evidence is ready; recheck', choice='retry')
    assert co.db.one('SELECT count(*) AS n FROM tasks')['n'] == count
    assert co.pipeline.advance(p['id'])['stage'] == 'release_approval'


def test_wait_endpoint_is_cto_only_and_preserves_work(co):
    p = co.pipeline.create_project('Wait test', 'A library')
    co.db.run("UPDATE projects SET stage='build' WHERE id=?",p['id'])
    co.pipeline.pause(p['id'], co.s.cto_name)
    with TestClient(create_app(co, {'ceo': 'c', 'cto': 't'})) as client:
        path = f"/api/projects/{p['id']}/verification-wait"
        assert client.post(path,json={'body':'Use VoiceOver'},headers={'X-Token':'c'}).status_code == 403
        assert client.post(path,json={'body':' '},headers={'X-Token':'t'}).status_code == 400
        response=client.post(path,json={'body':'Use VoiceOver and record observed announcements'},headers={'X-Token':'t'})
        assert response.status_code == 200
        assert response.json()['stage'] == 'release_blocked'
        assert not co.db.one('SELECT id FROM tasks WHERE project_id=?',p['id'])
        assert 'VoiceOver' in co.pipeline.inbox('cto')[0]['summary']


def test_verification_blocker_cannot_hide_failed_acceptance(co):
    from vittics_builder.tools import ToolError
    agent=co.org.agent('Badri')
    for entries in ([],[{'criterion':'Core','status':'failed','evidence':'Observed crash'}]):
        with pytest.raises(ToolError,match='Verification-only'):
            co.runtime._execute(agent,'submit_review',{'score':50,'verdict':'request_changes',
                'blocker_type':'verification','acceptance':entries},None,RunResult(),None,{},0)


def test_wait_refuses_to_race_active_project(co):
    import threading
    p=co.pipeline.create_project('Busy', 'A library')
    lock=co.pipeline._locks.setdefault(p['id'],threading.Lock())
    with lock:
        with pytest.raises(PipelineError,match='Pause the project'):
            co.pipeline.wait_for_verification(p['id'],co.s.cto_name,'Missing manual checks')
