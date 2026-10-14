"""Create an artifact manifest; hashes establish identity, not notarization or reproducibility."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def manifest(root, artifacts):
    root = Path(root).resolve()
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=root, text=True).strip()
    commit = git('rev-parse', 'HEAD')
    if git('status', '--porcelain', '--untracked-files=no'):
        raise ValueError('Tracked source has uncommitted changes.')
    entries = []
    for path in sorted(map(Path, artifacts)):
        if not path.is_file() or path.is_symlink():
            raise ValueError(f'Artifact must be a regular file: {path}')
        entries.append({'name': path.name, 'bytes': path.stat().st_size, 'sha256': digest(path)})
    if not entries or len({e['name'] for e in entries}) != len(entries):
        raise ValueError('Provide artifacts with unique file names.')
    deps = {}
    for rel in ('pyproject.toml', 'desktop/package-lock.json', 'desktop/src-tauri/Cargo.lock'):
        if (root/rel).is_file():
            deps[rel] = digest(root/rel)
    return {'schema_version': 1, 'source_commit': commit, 'source_tree': git('rev-parse', 'HEAD^{tree}'),
            'artifacts': entries, 'dependency_file_hashes': deps,
            'runtime': {'python': platform.python_version(), 'platform': platform.platform()},
            'ci_run': os.environ.get('GITHUB_RUN_ID'),
            'limitations': ['Unsigned identity manifest, not an attestation.',
                            'Dependency file hashes do not prove all transitive versions are pinned.',
                            'Artifact identity does not prove clean installation or bit-reproducibility.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default='.')
    parser.add_argument('--output', required=True)
    parser.add_argument('artifacts', nargs='+')
    args = parser.parse_args()
    paths = []
    for pattern in args.artifacts:
        import glob
        matches = glob.glob(pattern)
        if not matches:
            parser.error(f'No artifacts match {pattern}')
        paths.extend(matches)
    report = manifest(args.root, paths)
    with open(args.output, 'x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write('\n')
