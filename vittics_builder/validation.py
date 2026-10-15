"""Executable product acceptance contracts and durable release evidence."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import platform
import sys
from types import CodeType

from .db import now
from .tools import ToolError, Workspace

CONTRACT = 'product.json'


def source_fingerprint(ws: Workspace) -> str:
    """Hash tracked inputs, excluding only the verifier's own generated report."""
    result = subprocess.run(['git', 'ls-files', '-z'], cwd=ws.root, capture_output=True, check=True)
    digest = hashlib.sha256()
    for raw in sorted(set(result.stdout.split(b'\0')) - {b''}):
        name = raw.decode('utf-8')
        if name == 'docs/VERIFICATION.json':
            continue
        path = ws.root / name
        if path.is_symlink():
            raise ValueError(f'Cannot verify symbolic link input: {name}')
        digest.update(raw + b'\0')
        digest.update(str(path.stat().st_mode & 0o111).encode() + b'\0')
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def _code_identity(value):
    if isinstance(value, CodeType):
        return {'bytecode': value.co_code.hex(), 'constants': [_code_identity(c) for c in value.co_consts],
                'names': value.co_names, 'variables': value.co_varnames, 'flags': value.co_flags,
                'args': (value.co_argcount, value.co_posonlyargcount, value.co_kwonlyargcount),
                'free': value.co_freevars, 'cells': value.co_cellvars,
                'exceptions': value.co_exceptiontable.hex()}
    if isinstance(value, tuple):
        return ['tuple', [_code_identity(v) for v in value]]
    if isinstance(value, frozenset):
        return ['frozenset', sorted(json.dumps(_code_identity(v), sort_keys=True) for v in value)]
    return [type(value).__name__, repr(value)]


def verifier_identity() -> dict:
    # Frozen desktop distributions need not ship Python source files. Fingerprint
    # the executing verifier code rather than assuming __file__ can be opened.
    code = [_code_identity(f.__code__) for f in (_code_identity, source_fingerprint, read_contract,
            validate_requirements, requirement_results, same_contract, verify_product)]
    return {'tool': 'vittics_builder.validation', 'python': sys.version,
            'platform': platform.platform(), 'sha256': hashlib.sha256(json.dumps(code, sort_keys=True).encode()).hexdigest()}


CONTRACT_GUIDE = '''Write product.json with this schema:
{"schema_version":2, "name":"Product", "setup":"installation instructions", "run":"how to start/use it",
 "requirements":[{"id":"FLOW-001", "description":"A concrete PRD acceptance criterion", "risk":"medium",
 "required_checks":["core-flow"]}],
 "checks":[{"id":"core-flow", "requirement":"A concrete PRD acceptance criterion",
 "command":"a finite shell command that exits nonzero on failure"}]}
For a web app or API, also add "serve": {"setup": "install command (optional)", "command": "start it
listening on $PORT and $HOST", "health": "/a path that answers 200 once it is ready"}: after sign-off it
runs on this computer as a preview people can open. Read API keys and secrets from environment variables.
Include automated checks for installation/build, tests, and the main end-to-end user flows
as applicable. Checks must exercise the real implementation, not stubs or unconditional success.
Map every executable requirement to stable requirement IDs and check IDs. Do not claim automated
checks establish manual accessibility, legal approval or security properties they do not exercise.
For servers, checks must start an isolated test instance and clean it up. Document required
external services, credentials, migrations, backups and deployment in docs/OPERATIONS.md.
Never include secrets. Include README.md with reproducible installation and usage instructions.
'''


def validate_plan(tasks: list[dict], roles: set[str]) -> None:
    if not isinstance(tasks, list) or not tasks:
        raise ValueError('The plan must contain tasks.')
    keys = set()
    for task in tasks:
        if not isinstance(task, dict):
            raise ValueError('Each task must be an object.')
        key = task.get('key', '')
        if not isinstance(key, str) or not re.fullmatch(r'[a-z0-9][a-z0-9_-]*', key) or key in keys:
            raise ValueError('Task keys must be unique lowercase identifiers.')
        keys.add(key)
        if task.get('role') not in roles:
            raise ValueError(f'Task {key} has an unstaffed builder role.')
        if not all(isinstance(task.get(k), str) and task[k].strip() for k in ('title', 'description')):
            raise ValueError(f'Task {key} needs a title and acceptance criteria in its description.')
    pending = {}
    for task in tasks:
        deps = task.get('depends_on', [])
        if not isinstance(deps, list) or any(not isinstance(d, str) or d not in keys for d in deps):
            raise ValueError(f"Task {task['key']} has unknown dependencies.")
        pending[task['key']] = set(deps)
    while pending:
        ready = {key for key, deps in pending.items() if not deps}
        if not ready:
            raise ValueError('The plan contains a dependency cycle.')
        pending = {key: deps - ready for key, deps in pending.items() if key not in ready}


def read_contract(ws: Workspace) -> dict:
    data = json.loads(ws.resolve(CONTRACT).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError('product.json must be an object.')
    for key in ('name', 'setup', 'run'):
        if not isinstance(data.get(key), str) or not data[key].strip():
            raise ValueError(f'product.json needs a nonempty {key}.')
    checks = data.get('checks')
    if not isinstance(checks, list) or not 1 <= len(checks) <= 30:
        raise ValueError('product.json needs 1–30 executable acceptance checks.')
    ids = set()
    for check in checks:
        if not isinstance(check, dict) or not all(isinstance(check.get(k), str) and check[k].strip()
                                                 for k in ('id', 'requirement', 'command')):
            raise ValueError('Every check needs id, requirement and command strings.')
        if check['id'] in ids:
            raise ValueError('Acceptance check ids must be unique.')
        ids.add(check['id'])
    validate_requirements(data)
    return data


def validate_requirements(contract: dict) -> None:
    """Validate explicit coverage without silently certifying legacy contracts."""
    if 'requirements' not in contract:
        if contract.get('schema_version', 1) != 1:
            raise ValueError('Version 2 contracts require a requirements registry.')
        return
    if contract.get('schema_version', 1) not in (1, 2):
        raise ValueError('Unsupported acceptance contract schema version.')
    requirements = contract['requirements']
    if not isinstance(requirements, list) or not requirements:
        raise ValueError('requirements must be a nonempty registry.')
    checks = {c['id'] for c in contract['checks']}
    seen = set()
    for requirement in requirements:
        if not isinstance(requirement, dict):
            raise ValueError('Each requirement must be an object.')
        key = requirement.get('id')
        if not isinstance(key, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', key) or key in seen:
            raise ValueError('Requirement IDs must be unique stable identifiers.')
        seen.add(key)
        if not isinstance(requirement.get('description'), str) or not requirement['description'].strip():
            raise ValueError(f'{key}: missing acceptance description.')
        if requirement.get('risk') not in ('low', 'medium', 'high'):
            raise ValueError(f'{key}: invalid risk.')
        required = requirement.get('required_checks')
        if not isinstance(required, list) or not required or any(not isinstance(c, str) or c not in checks for c in required):
            raise ValueError(f'{key}: every requirement needs known executable checks.')


def requirement_results(contract: dict, checks: list[dict]) -> list[dict]:
    outcomes = {c['id']: c['passed'] for c in checks}
    return [{**r, 'status': 'verified' if all(outcomes.get(c) is True for c in r['required_checks']) else 'unverified',
             'release_eligible': all(outcomes.get(c) is True for c in r['required_checks'])}
            for r in contract.get('requirements', [])]


def same_contract(current: str | None, approved: str | None) -> bool:
    """Whether product.json still says what the CTO approved: the same name, checks and serve command.
    Its description text (setup, run, release notes) may change without a new approval."""
    if current is None or approved is None:
        return current == approved
    try:
        a, b = json.loads(current), json.loads(approved)
    except ValueError:
        return current == approved
    if not isinstance(a, dict) or not isinstance(b, dict):
        return current == approved
    return all(a.get(k) == b.get(k) for k in ('schema_version', 'name', 'checks', 'serve', 'requirements'))


def verify_product(ws: Workspace, env: dict | None = None, redact=None, timeout: int | None = None,
                   record: bool = True, ids: list[str] | None = None) -> dict:
    """Run the acceptance checks on this computer. `env`: the project's keys; `redact` hides their values before
    anything is saved; `timeout`: seconds per check, which may exceed the agents' command limit; `record`: save
    docs/VERIFICATION.json (not for ticket reviews, whose parallel branches would conflict on it)."""
    report = {'checked_at': now(), 'passed': False, 'checks': [], 'errors': []}
    report['verifier'] = verifier_identity()
    contract = {}
    try:
        contract = read_contract(ws)
        report['contract_sha256'] = hashlib.sha256(ws.resolve(CONTRACT).read_bytes()).hexdigest()
        if ids is not None:
            available = {c['id'] for c in contract['checks']}
            if not isinstance(ids, list) or not ids or any(not isinstance(i, str) or i not in available for i in ids):
                raise ValueError('Use existing product.json check IDs.')
            contract['checks'] = [c for c in contract['checks'] if c['id'] in ids]
        for path in ('README.md', 'docs/OPERATIONS.md'):
            if not ws.resolve(path).is_file() or not ws.resolve(path).read_text(encoding="utf-8").strip():
                report['errors'].append(f'Missing delivery documentation: {path}')
        for check in contract['checks']:
            try:
                output = ws.run_command(check['command'], extra_env=env, timeout_seconds=timeout, max_seconds=timeout)
                if redact:
                    output = redact(output)
                passed = output.splitlines()[0] == 'exit code 0'
            except ToolError as exc:
                output, passed = str(exc), False
            report['checks'].append({**check, 'passed': passed, 'output': output})
    except (OSError, ValueError, ToolError) as exc:
        report['errors'].append(f'Invalid acceptance contract: {exc}')
    report['passed'] = bool(report['checks']) and not report['errors'] and all(c['passed'] for c in report['checks'])
    report['requirements'] = requirement_results(contract, report['checks']) if not report['errors'] else []
    report['coverage'] = 'explicit' if 'requirements' in contract else 'legacy-unmapped'
    report['release_eligible'] = report['passed'] and ids is None and all(r['release_eligible'] for r in report['requirements'])
    report['recorded'] = record
    if record:
        ws.write_file('docs/VERIFICATION.json', json.dumps(report, indent=2))
    return report


HOST_EVIDENCE = ("Vittics Builder ran the product's acceptance checks (product.json) on this computer, outside "
                 "your sandbox, on the current files:\n{results}\n{saved}"
                 "Treat these results as the runtime evidence. Your own sandbox may block Docker, databases, local "
                 "ports or browsers: never request changes only because you could not run something yourself.")


def evidence(report: dict, tail: int = 1500) -> str:
    """The checks' results for an agent's prompt: each check's outcome, and the end of a failing check's output."""
    lines = [f"- Not checked: {e}" for e in report['errors']]
    for c in report['checks']:
        lines.append(f"- {c['id']}: {'PASSED' if c['passed'] else 'FAILED'} (`{c['command']}`)")
        if not c['passed']:
            lines.append("  " + c['output'][-tail:].replace("\n", "\n  "))
    return HOST_EVIDENCE.format(results="\n".join(lines) or "- No checks are defined yet.",
                                saved="Full output: docs/VERIFICATION.json.\n" if report.get('recorded') else "")
