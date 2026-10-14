from vittics_builder.repository import index, impact


def test_transitive_imports_and_invalidation(tmp_path):
    (tmp_path/'core.py').write_text('def total(): return 1')
    (tmp_path/'app.py').write_text('from core import total')
    (tmp_path/'test_app.py').write_text('import app')
    first = index(tmp_path)
    assert first['files']['core.py']['symbols'] == ['total']
    assert impact(first, ['core.py'])['tests'] == ['test_app.py']
    assert impact(first, ['core.py'])['mode'] == 'selected'
    (tmp_path/'core.py').write_text('def total(): return 2')
    assert index(tmp_path)['digest'] != first['digest']
    (tmp_path/'core.py').unlink()
    assert impact(index(tmp_path), ['core.py'])['mode'] == 'full'


def test_relative_import_and_package_initialization(tmp_path):
    p = tmp_path/'pkg'; p.mkdir()
    (p/'__init__.py').write_text('')
    (p/'core.py').write_text('x=1')
    (p/'api.py').write_text('from . import core')
    (tmp_path/'test_api.py').write_text('import pkg.api')
    inventory = index(tmp_path)
    assert 'pkg/core.py' in inventory['dependencies']['pkg/api.py']
    assert 'pkg/__init__.py' in inventory['dependencies']['test_api.py']
    assert impact(inventory, ['pkg/core.py'])['tests'] == ['test_api.py']


def test_unknown_and_dynamic_fallback(tmp_path):
    (tmp_path/'test_app.py').write_text('__import__("app")')
    inventory = index(tmp_path)
    assert impact(inventory, ['test_app.py'])['mode'] == 'full'
    assert impact(inventory, ['package.json'])['mode'] == 'full'
    assert impact(inventory, [])['mode'] == 'full'


def test_symlink_outside_root_not_read(tmp_path):
    (tmp_path/'secret.py').symlink_to('/etc/passwd')
    assert index(tmp_path)['files'] == {}
