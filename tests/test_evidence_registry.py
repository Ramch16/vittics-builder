import json

import pytest

from vittics_builder.tools import Workspace
from vittics_builder.validation import read_contract, requirement_results, same_contract, source_fingerprint, verify_product
from test_validation import contract
from test_validation import start_build
from test_pipeline import decide_next
from vittics_builder.pipeline import PipelineError
from vittics_builder import validation


def registered(ws):
    contract(ws)
    data = json.loads(ws.read_file('product.json'))
    data['requirements'] = [{'id': 'FLOW-001', 'description': 'Core flow works', 'risk': 'medium',
                             'required_checks': ['flow'], 'status': 'verified'}]
    ws.write_file('product.json', json.dumps(data))
    return data


@pytest.mark.parametrize('checks', [[], ['missing'], [None]])
def test_missing_evidence_mapping_rejected(tmp_path, checks):
    ws = Workspace(tmp_path)
    data = registered(ws)
    data['requirements'][0]['required_checks'] = checks
    ws.write_file('product.json', json.dumps(data))
    with pytest.raises(ValueError):
        read_contract(ws)


def test_agent_claim_cannot_verify_requirement(tmp_path):
    ws = Workspace(tmp_path)
    data = registered(ws)
    result = requirement_results(data, [{'id': 'flow', 'passed': False}])
    assert result[0]['status'] == 'unverified'
    assert not result[0]['release_eligible']
    assert not requirement_results(data, [])[0]['release_eligible']


def test_registry_change_requires_approval(tmp_path):
    data = registered(Workspace(tmp_path))
    original = json.dumps(data)
    data['requirements'][0]['risk'] = 'low'
    assert not same_contract(original, json.dumps(data))


def test_partial_check_run_is_not_release_evidence(tmp_path):
    ws = Workspace(tmp_path)
    registered(ws)
    result = verify_product(ws, ids=['flow'])
    assert result['passed']
    assert not result['release_eligible']
    assert verify_product(ws)['release_eligible']


def test_documentation_code_changes_invalidate_evidence(tmp_path):
    ws = Workspace(tmp_path)
    ws.init_repo()
    registered(ws)
    ws.write_file('docs/example.py', 'answer = 42')
    ws.commit('Candidate')
    original = source_fingerprint(ws)
    ws.write_file('docs/example.py', 'answer = 0')
    assert source_fingerprint(ws) != original


def test_legacy_coverage_not_misrepresented(tmp_path):
    ws = Workspace(tmp_path)
    contract(ws)
    assert verify_product(ws)['coverage'] == 'legacy-unmapped'


def test_new_contract_cannot_omit_registry(tmp_path):
    ws = Workspace(tmp_path)
    contract(ws)
    data = json.loads(ws.read_file('product.json'))
    data['schema_version'] = 2
    ws.write_file('product.json', json.dumps(data))
    assert not verify_product(ws)['passed']


def test_missing_ledger_blocks_release_despite_workspace_report(co):
    start_build(co)
    decide_next(co, 'cto')
    approval = next(a for a in co.pipeline.inbox('cto') if a['kind'] == 'release')
    payload = json.loads(approval['payload'])
    assert payload['ledger_id']
    co.db.run('DELETE FROM verification_runs WHERE id=?', payload['ledger_id'])
    with pytest.raises(PipelineError, match='evidence is missing'):
        co.pipeline.decide(approval['id'], 'cto', 'approved')


def test_failed_ledger_blocks_release(co):
    start_build(co)
    decide_next(co, 'cto')
    approval = next(a for a in co.pipeline.inbox('cto') if a['kind'] == 'release')
    payload = json.loads(approval['payload'])
    row = co.db.one('SELECT * FROM verification_runs WHERE id=?', payload['ledger_id'])
    proof = json.loads(row['report'])
    proof['release_eligible'] = False
    co.db.run('UPDATE verification_runs SET report=? WHERE id=?', json.dumps(proof), row['id'])
    with pytest.raises(PipelineError, match='evidence is missing'):
        co.pipeline.decide(approval['id'], 'cto', 'approved')


def test_source_modified_during_checks_fails_even_when_command_passes(co, monkeypatch):
    p = start_build(co)
    decide_next(co, 'cto')
    ws = co.pipeline.workspace(p)
    original = ws.run_command

    def mutate(*args, **kwargs):
        result = original(*args, **kwargs)
        ws.write_file('README.md', 'Changed during verification')
        return result

    monkeypatch.setattr(ws, 'run_command', mutate)
    report = co.pipeline._host_checks(p, ws)
    assert not report['passed']
    assert not report['release_eligible']
    assert 'changed during verification' in ' '.join(report['errors'])
    row = co.db.one('SELECT report FROM verification_runs WHERE id=?', report['ledger_id'])
    assert not json.loads(row['report'])['passed']


def test_verifier_identity_does_not_require_unbundled_source(monkeypatch):
    before = validation.verifier_identity()
    monkeypatch.setattr(validation, '__file__', '/missing/frozen/validation.py')
    assert validation.verifier_identity() == before
