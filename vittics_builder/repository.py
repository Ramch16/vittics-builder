"""Content-addressed Python repository inventory and conservative impact reports.

This never executes repository code. Unsupported/dynamic dependencies force a
full-suite recommendation; selected tests are advisory, never release evidence.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import sys
from pathlib import Path

SKIP = {'.git', '.venv', 'venv', 'node_modules', '__pycache__', 'dist', 'build', '.pytest_cache'}


def index(root):
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError('Repository path must be an existing directory.')
    files, modules, edges, unknown = {}, {}, {}, []
    contents = {}
    for parent, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in SKIP and not (Path(parent)/d).is_symlink())
        for name in sorted(names):
            path = Path(parent)/name
            if path.is_symlink() or path.suffix != '.py':
                continue
            rel = path.relative_to(root).as_posix()
            if path.stat().st_size > 5_000_000:
                unknown.append(f'{rel}: exceeds 5 MB index limit')
                continue
            data = path.read_bytes()
            contents[rel] = data
            files[rel] = {'sha256': hashlib.sha256(data).hexdigest(), 'symbols': []}
            module = rel[:-3].replace('/', '.')
            if module.endswith('.__init__'):
                module = module[:-9]
            if module in modules:
                unknown.append(f'ambiguous module: {module}')
            modules[module] = rel
    for module, rel in sorted(modules.items()):
        edges[rel] = []
        try:
            tree = ast.parse(contents[rel], filename=rel)
        except (SyntaxError, UnicodeError) as exc:
            unknown.append(f'{rel}: {type(exc).__name__}')
            continue
        files[rel]['symbols'] = sorted({n.name for n in ast.walk(tree)
                                       if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))})
        package = module if rel.endswith('/__init__.py') else module.rpartition('.')[0]
        for node in ast.walk(tree):
            imports = []
            if isinstance(node, ast.Import):
                imports = [n.name for n in node.names]
            elif isinstance(node, ast.ImportFrom):
                prefix = node.module or ''
                if node.level:
                    parts = package.split('.') if package else []
                    if node.level > len(parts):
                        unknown.append(f'{rel}: unresolved relative import')
                        continue
                    prefix = '.'.join(parts[:len(parts)-node.level+1] + ([prefix] if prefix else []))
                imports = [prefix] + [prefix+'.'+n.name for n in node.names if n.name != '*']
                if any(n.name == '*' for n in node.names):
                    unknown.append(f'{rel}: wildcard import')
            elif isinstance(node, ast.Call):
                name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, 'attr', '')
                if name in {'__import__', 'import_module', 'exec', 'eval'}:
                    unknown.append(f'{rel}: dynamic code/import')
            for imported in imports:
                # Importing a submodule also executes its package initializers.
                parts = imported.split('.')
                if (parts[0] not in sys.stdlib_module_names and
                        not any('.'.join(parts[:n]) in modules for n in range(1, len(parts)+1))):
                    unknown.append(f'{rel}: unresolved dependency {imported}')
                for size in range(1, len(parts)+1):
                    target = modules.get('.'.join(parts[:size]))
                    if target and target != rel:
                        edges[rel].append(target)
        edges[rel] = sorted(set(edges[rel]))
    payload = {'schema_version': 1, 'language': 'python', 'files': files,
               'dependencies': edges, 'uncertainties': sorted(set(unknown))}
    payload['digest'] = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    return payload


def impact(inventory, changed):
    files = inventory['files']
    reasons = list(inventory['uncertainties'])
    if not changed:
        reasons.append('No changed-file list supplied')
    for path in changed:
        if path not in files:
            reasons.append(f'Unknown, deleted or unsupported file: {path}')
        if Path(path).name in {'conftest.py', '__init__.py'}:
            reasons.append(f'Shared Python configuration/package: {path}')
    affected = set(changed) & files.keys()
    while True:
        more = {src for src, deps in inventory['dependencies'].items() if set(deps) & affected}
        if more <= affected:
            break
        affected |= more
    tests = sorted(p for p in affected if Path(p).name.startswith('test_'))
    if not tests:
        reasons.append('No statically linked tests found')
    return {'mode': 'full' if reasons else 'selected', 'tests': tests,
            'affected': sorted(affected), 'reasons': sorted(set(reasons)),
            'inventory_digest': inventory['digest'],
            'advisory': True, 'release_requires_full_acceptance': True}
