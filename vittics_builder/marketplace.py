"""Checksum-pinned agent/skill packages; no install hooks or executable plugin payloads."""
import hashlib
import json
import re

from .db import now
from .operations_store import atomic
from .org import KINDS
from .tools import TOOL_SPECS

NAME=re.compile(r'^[a-z0-9][a-z0-9_-]*(?:/[a-z0-9][a-z0-9_-]*)?$')


def digest(manifest,assets):
    return hashlib.sha256(json.dumps({'manifest':manifest,'assets':assets},sort_keys=True,separators=(',',':')).encode()).hexdigest()


class Marketplace:
    def __init__(self,company):self.co,self.db=company,company.db

    def register(self,manifest,assets):
        if not isinstance(manifest,dict) or not NAME.fullmatch(str(manifest.get('name',''))) or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+',str(manifest.get('version',''))):
            raise ValueError('Package needs a namespaced name and semantic version.')
        if set(manifest)-{'name','version','description','roles','departments'}:raise ValueError('Unsupported manifest fields; executable hooks are not permitted.')
        departments=manifest.get('departments') or []
        roles=manifest.get('roles') or []
        if not isinstance(departments,list) or not isinstance(roles,list):raise ValueError('Departments and roles must be lists.')
        for d in departments:
            if (not isinstance(d,dict) or set(d)-{'id','name','reports_to'}
                    or not re.fullmatch(r'[a-z0-9][a-z0-9_-]*',str(d.get('id','')))
                    or not isinstance(d.get('name'),str) or not d['name'].strip() or len(d['name'])>100
                    or d.get('reports_to') not in ('ceo','cto')):
                raise ValueError('Department needs a safe id, name and CEO/CTO reporting line.')
        if len({d['id'] for d in departments})!=len(departments):raise ValueError('Duplicate department id.')
        if not isinstance(assets,dict) or not 1<=len(assets)<=20:raise ValueError('Package requires 1–20 Markdown skills.')
        for name,body in assets.items():
            if not re.fullmatch(r'[a-z0-9_-]+\.md',name) or not isinstance(body,str) or not 20<=len(body)<=50000:
                raise ValueError('Skills must be bounded Markdown files with safe names.')
        if len(json.dumps({'manifest':manifest,'assets':assets}))>500000:raise ValueError('Package exceeds 500KB.')
        for role in manifest.get('roles') or []:
            if not isinstance(role,dict) or set(role)-{'id','department','kind','tools','prompt','title'}:
                raise ValueError('Invalid agent role specification.')
            if not isinstance(role.get('department'),str) or not role['department'].strip():
                raise ValueError('Role requires a department identifier.')
            if not NAME.fullmatch(str(role.get('id',''))) or '/' in role['id'] or role.get('kind') not in KINDS:
                raise ValueError('Role needs a safe identifier and supported kind.')
            if (not isinstance(role.get('tools'),list) or any(not isinstance(t,str) or t not in TOOL_SPECS for t in role['tools'])
                    or not isinstance(role.get('prompt'),str) or not role['prompt'].strip() or len(role['prompt'])>50000
                    or role.get('title') is not None and (not isinstance(role['title'],str) or not role['title'].strip() or len(role['title'])>100)):
                raise ValueError('Role needs approved tools and a prompt.')
        if len({r['id'] for r in roles})!=len(roles):raise ValueError('Duplicate role id.')
        identity=manifest['name']+'@'+manifest['version'];pin=digest(manifest,assets)
        prior=self.db.one('SELECT * FROM marketplace WHERE name=?',identity)
        if prior and prior['digest']!=pin:raise ValueError('A published package version cannot change content.')
        if not prior:self.db.run('INSERT INTO marketplace(name,version,digest,manifest,assets,created_at) VALUES(?,?,?,?,?,?)',
                                 identity,manifest['version'],pin,json.dumps(manifest),json.dumps(assets),now())
        return {'name':identity,'sha256':pin,'manifest':manifest}

    def list(self):
        return self.db.all('SELECT name,version,digest,installed,created_at FROM marketplace ORDER BY name')

    def export_bundle(self,name):
        row=self.db.one('SELECT * FROM marketplace WHERE name=?',name)
        if not row:raise ValueError('No such package.')
        manifest,assets=json.loads(row['manifest']),json.loads(row['assets'])
        if digest(manifest,assets)!=row['digest']:raise ValueError('Stored package integrity check failed.')
        return {'schema_version':1,'sha256':row['digest'],'manifest':manifest,'assets':assets}

    def import_bundle(self,bundle,expected_sha256):
        if (not isinstance(bundle,dict) or set(bundle)!={'schema_version','sha256','manifest','assets'}
                or bundle.get('schema_version')!=1 or not isinstance(expected_sha256,str)
                or not re.fullmatch('[a-f0-9]{64}',expected_sha256)):
            raise ValueError('Import needs a version 1 bundle and a reviewed SHA256 pin.')
        if bundle['sha256']!=expected_sha256 or digest(bundle['manifest'],bundle['assets'])!=expected_sha256:
            raise ValueError('Package does not match the reviewed SHA256 pin.')
        return self.register(bundle['manifest'],bundle['assets'])

    def install(self,name,expected_sha256):
        row=self.db.one('SELECT * FROM marketplace WHERE name=?',name)
        if not row or row['digest']!=expected_sha256:raise ValueError('Package does not match the reviewed SHA256 pin.')
        if row['installed']:return {'name':name,'installed':True,'already_installed':True}
        manifest,assets=json.loads(row['manifest']),json.loads(row['assets'])
        if digest(manifest,assets)!=expected_sha256:raise ValueError('Stored package integrity check failed.')
        folder=self.co.s.root/'skills'
        if self.co.s.root not in folder.resolve().parents:raise ValueError('Skill directory escapes the company.')
        folder.mkdir(exist_ok=True)
        prefix=re.sub(r'[^a-z0-9_-]','-',name)
        targets={folder/(prefix+'-'+n):v for n,v in assets.items()}
        if any(p.exists() for p in targets):raise ValueError('Installation would overwrite a company skill.')
        roles=manifest.get('roles') or []
        departments=manifest.get('departments') or []
        proposed={d['id']:d for d in departments}
        for d in departments:
            existing=self.db.one('SELECT * FROM departments WHERE id=?',d['id'])
            if existing and any(existing[k]!=d[k] for k in ('name','reports_to')):
                raise ValueError('Package would change an existing department.')
        for role in roles:
            if self.db.one('SELECT id FROM roles WHERE id=?',role['id']):raise ValueError('Installation would overwrite an existing role.')
            if not self.db.one('SELECT id FROM departments WHERE id=?',role['department']) and role['department'] not in proposed:raise ValueError('Package targets an unknown department.')
        created=[]
        try:
            with atomic(self.db):
                for d in departments:
                    if not self.db.one('SELECT id FROM departments WHERE id=?',d['id']):
                        self.co.org.add_department(d['id'],d['name'],d['reports_to'])
                for path,body in targets.items():
                    with path.open('x') as target:target.write(body)
                    created.append(path)
                for r in roles:self.co.org.add_role(r['id'],r['department'],r['kind'],r['tools'],r['prompt'],r.get('title'))
                self.db.run('UPDATE marketplace SET installed=1 WHERE name=?',name)
                self.db.log('marketplace',f'Installed pinned package {name}.',actor='CEO')
        except BaseException:
            for path in created:path.unlink(missing_ok=True)
            raise
        return {'name':name,'installed':True,'skills':[p.name for p in targets],'roles':[r['id'] for r in roles]}
