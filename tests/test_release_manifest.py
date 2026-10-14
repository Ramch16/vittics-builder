import importlib.util
from pathlib import Path
import subprocess

import pytest

spec = importlib.util.spec_from_file_location('release_manifest',
    Path(__file__).parents[1]/'desktop/scripts/release_manifest.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_manifest_hashes_and_dirty_source(tmp_path):
    def git(*args):
        subprocess.run(['git', *args], cwd=tmp_path, check=True, capture_output=True)
    git('init')
    git('config', 'user.email', 'test@example.test')
    git('config', 'user.name', 'Test')
    (tmp_path/'pyproject.toml').write_text('# test')
    git('add', '.')
    git('commit', '-m', 'fixture')
    artifact = tmp_path/'installer.exe'
    artifact.write_bytes(b'installer fixture')
    result = module.manifest(tmp_path, [artifact])
    assert result['artifacts'][0]['sha256'] == module.digest(artifact)
    assert result['dependency_file_hashes']['pyproject.toml'] == module.digest(tmp_path/'pyproject.toml')
    assert len(result['source_commit']) == 40
    with pytest.raises(ValueError):
        module.manifest(tmp_path, [artifact, artifact])
    (tmp_path/'pyproject.toml').write_text('# modified')
    with pytest.raises(ValueError, match='uncommitted'):
        module.manifest(tmp_path, [artifact])
