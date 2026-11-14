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
    with pytest.raises(PipelineError, match='Nothing in the product has changed'):    # same source: QA would stop again
        co.pipeline.decide(pending['id'], 'cto', 'rejected', 'Recheck', choice='retry')
    ws = co.pipeline.workspace(co.pipeline.project(p['id']))
    ws.write_file('docs/HUMAN_CHECKS.md', 'VoiceOver announced each error.\n')
    ws.commit('Record the human checks')
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


def block_on_verification(co, monkeypatch):
    original = co.runtime.run
    calls = []
    def run(agent, *args, **kwargs):
        if (kwargs.get('meta') or {}).get('purpose') == 'integration':
            calls.append(1)
            return RunResult(completed=True, review={'score': 85, 'verdict': 'request_changes',
                'blocker_type': 'verification', 'notes': 'Check 200% zoom and keys by hand.',
                'acceptance': [{'criterion': 'Zoom', 'status': 'unverified', 'evidence': 'No device'}]})
        return original(agent, *args, **kwargs)
    monkeypatch.setattr(co.runtime, 'run', run)
    p = start_build(co)
    assert decide_next(co, 'cto')['stage'] == 'release_blocked'
    pending = next(a for a in co.pipeline.inbox('cto') if a['kind'] == 'release_blocked')
    return p, pending, calls


def test_the_cto_can_accept_checks_only_a_person_can_do(co, monkeypatch):
    p, pending, calls = block_on_verification(co, monkeypatch)
    assert len(calls) == 1
    with pytest.raises(PipelineError, match='Say why'):
        co.pipeline.decide(pending['id'], 'cto', 'approved', '', choice='accept')
    co.pipeline.decide(pending['id'], 'cto', 'approved', 'A personal tool; I tried it myself', choice='accept')
    assert co.pipeline.advance(p['id'])['stage'] == 'release_approval'
    assert len(calls) == 1                                           # QA was not run again
    [release] = [a for a in co.pipeline.inbox('cto') if a['kind'] == 'release']
    assert 'Not checked by a person' in release['summary'] and 'I tried it myself' in release['summary']
    assert co.db.one("SELECT 1 FROM events WHERE message LIKE '%accepted the checks only a person can do%'")


def test_an_acceptance_covers_only_the_source_that_was_accepted(co, monkeypatch):
    p, pending, calls = block_on_verification(co, monkeypatch)
    co.pipeline.decide(pending['id'], 'cto', 'approved', 'Fine for me', choice='accept')
    ws = co.pipeline.workspace(co.pipeline.project(p['id']))
    ws.write_file('app_change.txt', 'a new change after the acceptance\n')
    ws.commit('Change after acceptance')
    assert co.pipeline.advance(p['id'])['stage'] == 'release_blocked'
    assert len(calls) == 2                                           # changed code: QA looks again


def test_failed_checks_cannot_be_accepted(co):
    p = co.pipeline.create_project('Failing', 'A library')
    aid = co.pipeline._approval(p['id'], 'release_blocked', 'cto', 'Release checks failed for Failing', 'Tests failed', {})
    with pytest.raises(PipelineError, match='Only checks that need a person'):
        co.pipeline.decide(aid, 'cto', 'approved', 'Ship it', choice='accept')
