import asyncio
import copy
import json
import os
import socket
import subprocess
import sys
import time

import pytest
from fastapi.testclient import TestClient

from vittics_builder.company import Company
from vittics_builder.integrations import Integrations
from vittics_builder.llm import MockProvider
from vittics_builder.org import OrgError
from vittics_builder.tools import ToolError, Workspace


def package():
    return {'name':'community/research','version':'1.0.0',
            'departments':[{'id':'research','name':'Research','reports_to':'cto'}],
            'roles':[{'id':'researcher','department':'research','kind':'advisor',
                      'title':'Researcher','tools':['read_file'],'prompt':'Review evidence and cite sources.'}]}, {
            'research.md':'# Research\nDistinguish observed evidence from assumptions.'}


def test_team_bundle_roundtrip_and_integrity(co, tmp_path):
    manifest, assets = package()
    registered = co.marketplace.register(manifest, assets)
    bundle = co.marketplace.export_bundle(registered['name'])
    other = Company(tmp_path/'other', provider=MockProvider(), create=True)
    assert other.marketplace.import_bundle(bundle, registered['sha256'])['sha256'] == registered['sha256']
    assert not other.db.one("SELECT 1 FROM departments WHERE id='research'")
    other.marketplace.install(registered['name'], registered['sha256'])
    assert other.org.role('researcher')['department'] == 'research'
    assert other.db.one("SELECT name FROM departments WHERE id='research'")['name'] == 'Research'
    bad = copy.deepcopy(bundle)
    bad['manifest']['departments'][0]['reports_to'] = 'ceo'
    with pytest.raises(ValueError, match='pin'):
        co.marketplace.import_bundle(bad, registered['sha256'])
    assert len(co.marketplace.list()) == 1


def test_team_install_does_not_overwrite_departments(co):
    m,a=package();co.org.add_department('research','Existing research','ceo')
    p=co.marketplace.register(m,a)
    with pytest.raises(ValueError,match='existing department'):
        co.marketplace.install(p['name'],p['sha256'])
    assert not co.db.one("SELECT 1 FROM roles WHERE id='researcher'")
    assert not list((co.s.root/'skills').glob('*.md'))


def test_team_install_rolls_back_departments_and_skills(co, monkeypatch):
    m,a=package();p=co.marketplace.register(m,a)
    def fail(*args,**kwargs):raise RuntimeError('Injected role failure')
    monkeypatch.setattr(co.org,'add_role',fail)
    with pytest.raises(RuntimeError):co.marketplace.install(p['name'],p['sha256'])
    assert not co.db.one("SELECT 1 FROM departments WHERE id='research'")
    assert not list((co.s.root/'skills').glob('*.md'))
    assert co.marketplace.list()[0]['installed'] == 0


def test_edit_and_reassign_preserves_identity_and_blocks_busy_work(co):
    co.org.add_department('research','Research','cto')
    co.org.add_role('researcher','research','builder',['read_file'],'Review evidence.')
    agent=co.org.staff(role='backend_engineer')[0]
    moved=co.org.reassign(agent['id'],'researcher',by='CEO')
    for key in ('id','name','seat','model'):assert moved[key]==agent[key]
    co.org.update_department('research',name='Research lab',reports_to='ceo')
    changed=co.org.update_role('researcher',title='Senior researcher',tools=[],prompt='Write reports.')
    assert changed['title']=='Senior researcher' and json.loads(changed['tools'])==[]
    rid=co.runs.start(moved,None,None,'research','Run')
    with pytest.raises(OrgError,match='running'):co.org.update_department('research',name='Busy')
    with pytest.raises(OrgError,match='running'):co.org.reassign(agent['id'],'backend_engineer')
    co.runs.finish(rid,'completed')
    p=co.pipeline.create_project('Queued','A library')
    ticket=co.tickets.create(p['id'],'Research','Investigate','CEO',status='todo',role='researcher')
    co.db.run('UPDATE tasks SET assignee_id=? WHERE id=?',agent['id'],ticket['id'])
    with pytest.raises(OrgError,match='unfinished'):co.org.reassign(agent['id'],'backend_engineer')
    with pytest.raises(OrgError):co.org.update_role('researcher',tools=['unknown'])


def test_org_and_package_api_permissions(co):
    client=TestClient(create_app(co,{'ceo':'ceo','cto':'cto'}))
    ceo={'X-Token':'ceo'};cto={'X-Token':'cto'}
    assert client.post('/api/organization/departments',json={'id':'research','name':'Research','reports_to':'cto'},headers=cto).status_code==403
    assert client.post('/api/organization/departments',json={'id':'research','name':'Research','reports_to':'cto'},headers=ceo).status_code==200
    assert client.patch('/api/organization/departments/research',json={'name':'Lab'},headers=cto).status_code==200
    assert client.patch('/api/organization/departments/research',json={'reports_to':'ceo'},headers=cto).status_code==403
    assert client.patch('/api/organization/roles/backend_engineer',json={'department':'product'},headers=cto).status_code==403
    assert client.patch('/api/organization/roles/product_manager',json={'department':'engineering'},headers=cto).status_code==403
    agent=co.org.staff(role='backend_engineer')[0]
    assert client.post(f"/api/agents/{agent['id']}/reassign",json={'role':'product_manager'},headers=cto).status_code==403
    m,a=package();p=co.marketplace.register(m,a)
    assert client.get('/api/marketplace/export',params={'name':p['name']},headers=cto).status_code==403
    bundle=client.get('/api/marketplace/export',params={'name':p['name']},headers=ceo).json()
    assert client.post('/api/marketplace/import',json={'bundle':bundle,'sha256':p['sha256']},headers=cto).status_code==403
    assert client.post('/api/marketplace/import',json={'bundle':bundle,'sha256':p['sha256']},headers=ceo).status_code==200


from vittics_builder.server import create_app


def test_integration_inventory_redacts_and_disabled_servers_stay_blocked(co, monkeypatch):
    monkeypatch.setenv('SERVICE_AUTH','Bearer super-private')
    co.s.raw['tools']={'mcp':{'remote':{'transport':'streamable_http','url':'https://example.com/private',
                         'headers_env':{'Authorization':'SERVICE_AUTH'},'enabled':False,
                         'roles':['qa_engineer'],'tools':['echo']}}}
    adapter=Integrations(co.s)
    assert not adapter.allowed('qa_engineer','mcp_call')
    assert 'super-private' not in json.dumps(adapter.inventory())
    assert 'example.com' not in json.dumps(adapter.inventory())
    monkeypatch.delenv('SERVICE_AUTH')
    assert adapter.inventory()[0]['missing_credentials']==['SERVICE_AUTH']
    with pytest.raises(ToolError):adapter.call('qa_engineer','mcp_call',{'server':'remote','tool':'echo'},Workspace(co.s.root/'test'))


@pytest.mark.parametrize('url',['http://external.example/mcp','https://user:password@example.com/mcp',
                                'https://example.com/mcp?token=secret','file:///etc/passwd'])
def test_remote_mcp_rejects_unsafe_endpoint_configuration(co,url):
    pytest.importorskip('mcp')
    adapter=Integrations(co.s)
    async def enter():
        async with adapter._transport({'transport':'streamable_http','url':url},Workspace(co.s.root/'ws')):
            pytest.fail('Unsafe transport entered')
    with pytest.raises(ToolError,match='HTTPS'):asyncio.run(enter())


def test_real_remote_mcp_discovery_and_call(co,tmp_path,monkeypatch):
    pytest.importorskip('mcp')
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    server=tmp_path/'remote_mcp.py'
    server.write_text('''from mcp.server.fastmcp import FastMCP, Context
import sys
mcp=FastMCP("Remote test",host="127.0.0.1",port=int(sys.argv[1]),stateless_http=True,json_response=True)
@mcp.tool()
def echo(message: str, ctx: Context) -> str:
    assert ctx.request_context.request.headers.get("authorization") == "Bearer fixture-token"
    return "remote: " + message
@mcp.tool()
def forbidden() -> str:
    return "not permitted"
mcp.run(transport="streamable-http")
''')
    process=subprocess.Popen([sys.executable,str(server),str(port)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            if process.poll() is not None:pytest.fail('MCP fixture server exited')
            try:
                with socket.create_connection(('127.0.0.1',port),timeout=.1):break
            except OSError:time.sleep(.05)
        else:pytest.fail('MCP fixture did not start')
        monkeypatch.setenv('REMOTE_HEADER','Bearer fixture-token')
        co.s.raw['tools']={'mcp':{'remote':{'transport':'streamable_http','url':f'http://127.0.0.1:{port}/mcp',
                           'headers_env':{'Authorization':'REMOTE_HEADER'},'roles':['qa_engineer'],'tools':['echo']}}}
        adapter=Integrations(co.s);ws=Workspace(tmp_path/'ws')
        listing=json.loads(adapter.call('qa_engineer','mcp_list_tools',{'server':'remote'},ws))
        assert [x['name'] for x in listing]==['echo']
        result=json.loads(adapter.call('qa_engineer','mcp_call',{'server':'remote','tool':'echo','arguments':{'message':'hello'}},ws))
        assert 'remote: hello' in json.dumps(result)
        with pytest.raises(ToolError,match='allowlist'):
            adapter.call('qa_engineer','mcp_call',{'server':'remote','tool':'forbidden'},ws)
        with pytest.raises(ToolError,match='role'):
            adapter.call('backend_engineer','mcp_list_tools',{'server':'remote'},ws)
    finally:
        process.terminate()
        try:process.wait(timeout=5)
        except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)


def test_reference_packages_and_cli_roundtrip(co,tmp_path,capsys):
    from pathlib import Path
    from vittics_builder.cli import main
    for path in sorted((Path(__file__).parents[1]/'examples'/'teams').glob('*.json')):
        bundle=json.loads(path.read_text())
        assert main(['--home',str(co.s.root),'marketplace','import','--bundle',str(path),
                     '--sha256',bundle['sha256']])==0
        capsys.readouterr()
        name=bundle['manifest']['name']+'@'+bundle['manifest']['version']
        output=tmp_path/(path.stem+'-export.json')
        assert main(['--home',str(co.s.root),'marketplace','export','--name',name,'--bundle',str(output)])==0
        capsys.readouterr()
        assert json.loads(output.read_text())==bundle
        assert main(['--home',str(co.s.root),'marketplace','export','--name',name,'--bundle',str(output)])==1
        capsys.readouterr()
        assert co.marketplace.install(name,bundle['sha256'])['installed']


def test_remote_redirect_does_not_forward_credentials(co,monkeypatch):
    pytest.importorskip('mcp')
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    received=[]
    class Redirect(BaseHTTPRequestHandler):
        def do_POST(self):
            received.append(self.path)
            self.send_response(307)
            self.send_header('Location','/leaked')
            self.send_header('Content-Length','0')
            self.end_headers()
        def log_message(self,*args):pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Redirect)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    monkeypatch.setenv('REMOTE_AUTH','Bearer never-redirect')
    co.s.raw['tools']={'mcp':{'redirect':{'transport':'streamable_http',
        'url':f'http://127.0.0.1:{server.server_port}/redirect','headers_env':{'Authorization':'REMOTE_AUTH'},
        'roles':['qa_engineer'],'tools':['echo']}}}
    try:
        with pytest.raises(ToolError) as error:
            Integrations(co.s).call('qa_engineer','mcp_list_tools',{'server':'redirect'},Workspace(co.s.root/'ws'))
        assert '/leaked' not in received
        assert 'never-redirect' not in str(error.value)
    finally:
        server.shutdown();server.server_close();thread.join(timeout=5)
