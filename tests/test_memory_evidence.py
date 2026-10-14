import pytest


def test_changed_deleted_and_revalidated_evidence(co):
    p = co.pipeline.create_project('Evidence', 'Test file evidence')
    ws = co.pipeline.workspace(p)
    ws.write_file('api.py', 'VERSION=1')
    co.memory.remember('The API contract uses version one', 'tester', p['id'], evidence_files=['api.py'])
    assert co.memory.search(p['id'], 'contract')
    ws.write_file('api.py', 'VERSION=2')
    assert not co.memory.search(p['id'], 'contract')
    co.memory.remember('The API contract uses version one', 'tester', p['id'], evidence_files=['api.py'])
    assert co.memory.search(p['id'], 'contract')
    ws.resolve('api.py').unlink()
    assert not co.memory.recall(p['id'], 'contract')


@pytest.mark.parametrize('path', ['../org.yaml', '/etc/passwd', 'missing.py'])
def test_evidence_cannot_escape_or_be_missing(co, path):
    p = co.pipeline.create_project('Evidence', 'Test file evidence')
    with pytest.raises(ValueError):
        co.memory.remember('An evidenced fact', 'tester', p['id'], evidence_files=[path])


def test_company_evidence_rejected(co):
    with pytest.raises(ValueError):
        co.memory.remember('An evidenced fact', 'tester', None, scope='company', evidence_files=['x.py'])


def test_evidence_survives_reopen(co):
    from vittics_builder.db import DB
    from vittics_builder.memory import Memory
    p = co.pipeline.create_project('Durable evidence', 'Test reopening')
    ws = co.pipeline.workspace(p)
    ws.write_file('api.py', 'VERSION=1')
    co.memory.remember('The contract is current', 'tester', p['id'], evidence_files=['api.py'])
    database_path = co.db.conn.execute('PRAGMA database_list').fetchone()[2]
    reopened = DB(database_path)
    try:
        assert Memory(reopened).search(p['id'], 'contract')
        ws.write_file('api.py', 'VERSION=2')
        assert not Memory(reopened).search(p['id'], 'contract')
    finally:
        reopened.conn.close()


def test_parallel_candidate_evidence_is_not_main_branch_evidence(co, tmp_path):
    p = co.pipeline.create_project('Candidate', 'Test isolated evidence')
    ws = co.pipeline.workspace(p)
    ws.write_file('api.py', 'VERSION=1')
    candidate = tmp_path/'candidate'; candidate.mkdir()
    (candidate/'api.py').write_text('VERSION=2')
    co.memory.remember('The contract uses version two', 'tester', p['id'],
                       evidence_files=['api.py'], evidence_root=candidate)
    assert not co.memory.search(p['id'], 'contract')
    ws.write_file('api.py', 'VERSION=2')
    assert co.memory.search(p['id'], 'contract')
