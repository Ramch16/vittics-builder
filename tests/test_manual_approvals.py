import json

import pytest
from fastapi.testclient import TestClient

from vittics_builder.server import create_app


@pytest.mark.parametrize('ceo,cto,stage', [
    (True, True, 'prd_approval'), (False, True, 'architecture_approval'),
    (True, False, 'prd_approval'), (False, False, 'done'),
])
def test_roles_independently_require_or_automate_approval(co, ceo, cto, stage):
    p = co.pipeline.create_project('Optional roles', 'A small library')
    ap = co.pipeline.autopilot
    ap.set_manual_approval(p['id'], 'ceo', ceo, 'Niki')
    ap.set_manual_approval(p['id'], 'cto', cto, 'Lucky')
    assert co.pipeline.advance(p['id'])['stage'] == stage
    if not ceo and not cto:
        signoff = co.db.one("SELECT * FROM approvals WHERE project_id=? AND kind='signoff'", p['id'])
        assert signoff['status'] == 'approved'
        assert signoff['decided_by'].startswith('Autopilot for ')
        assert json.loads(signoff['payload'])['verified_head']


def test_on_overrides_legacy_autopilot_and_is_persistent(co):
    p = co.pipeline.create_project('Manual', 'A small library')
    ap = co.pipeline.autopilot
    ap.set(p['id'], 'final', 'Niki')
    ap.set_manual_approval(p['id'], 'ceo', True, 'Niki')
    assert co.pipeline.advance(p['id'])['stage'] == 'prd_approval'
    from vittics_builder.autopilot import Autopilot
    assert Autopilot(co.pipeline).approval_overrides(p['id']) == {'ceo': True}


def test_automatic_signoff_cannot_accept_modified_source(co):
    from vittics_builder.pipeline import PipelineError
    p = co.pipeline.create_project('Verified', 'A small library')
    co.pipeline.autopilot.set(p['id'], 'final', 'Niki')
    assert co.pipeline.advance(p['id'])['stage'] == 'signoff'
    co.pipeline.workspace(co.pipeline.project(p['id'])).write_file('unexpected.txt', 'changed')
    co.pipeline.autopilot.set_manual_approval(p['id'], 'ceo', False, 'Niki')
    with pytest.raises(PipelineError, match='changed after verification'):
        co.pipeline.autopilot.step(p['id'])
    assert co.db.one("SELECT status FROM approvals WHERE project_id=? AND kind='signoff'", p['id'])['status'] == 'pending'


@pytest.mark.parametrize('kind', ['budget', 'deploy', 'release_blocked', 'escalation', 'hire', 'strategy', 'contract'])
def test_off_does_not_approve_exceptions(co, kind):
    p = co.pipeline.create_project('Exceptions', 'A small library')
    co.pipeline.autopilot.set_manual_approval(p['id'], 'ceo', False, 'Niki')
    co.pipeline._approval(p['id'], kind, 'ceo', 'Needs a person', 'Review this.', {})
    assert not co.pipeline.autopilot.step(p['id'])
    assert co.pipeline.inbox('ceo')[0]['status'] == 'pending'


def test_api_permissions_types_and_independent_toggles(co):
    p = co.pipeline.create_project('Controls', 'A small library')
    co.pipeline.pause(p['id'], 'Niki')
    tokens = {'ceo': 'ceo-token', 'cto': 'cto-token'}
    client = TestClient(create_app(co, tokens))
    url = f"/api/projects/{p['id']}/manual-approvals"
    ceo = {'X-Token': 'ceo-token'}
    cto = {'X-Token': 'cto-token'}
    assert client.post(url+'/cto', json={'required': False}, headers=ceo).status_code == 403
    assert client.post(url+'/ceo', json={'required': False}, headers=cto).status_code == 403
    for value in ['false', 0, None]:
        assert client.post(url+'/ceo', json={'required': value}, headers=ceo).status_code == 400
    assert client.post(url+'/ceo', json={'required': False}).status_code == 401
    assert client.post(url+'/ceo', json={'required': False}, headers=ceo).status_code == 200
    assert client.post(url+'/cto', json={'required': False}, headers=cto).status_code == 200
    assert client.post(url+'/ceo', json={'required': True}, headers=ceo).status_code == 200
    assert co.pipeline.autopilot.approval_overrides(p['id']) == {'ceo': True, 'cto': False}
    desktop = TestClient(create_app(co, tokens, desktop=True))
    assert desktop.post(url+'/cto', json={'required': True}, headers=ceo).status_code == 200
    assert co.pipeline.autopilot.approval_overrides(p['id']) == {'ceo': True, 'cto': True}
