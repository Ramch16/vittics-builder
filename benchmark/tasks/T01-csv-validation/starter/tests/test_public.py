import pytest
from app.csv_import import ImportRejected, import_rows


def test_imports_valid_rows():
    store = {}
    assert import_rows("id,name,email\n1,Ana,ana@example.com\n", store) == {"imported": 1}
    assert store == {"1": {"name": "Ana", "email": "ana@example.com"}}


def test_duplicate_id_is_rejected():
    with pytest.raises(ImportRejected):
        import_rows("id,name,email\n1,A,a@x.io\n1,B,b@x.io\n", {})
