import pytest
from app.csv_import import ImportRejected, import_rows


def test_no_partial_write_on_error():
    store = {"9": {"name": "Old", "email": "old@x.io"}}
    with pytest.raises(ImportRejected) as e:
        import_rows("id,name,email\n1,A,a@x.io\n2,,b@x.io\n", store)
    assert store == {"9": {"name": "Old", "email": "old@x.io"}}
    assert e.value.errors == ["line 3: empty name"] or any(m.startswith("line 3") for m in e.value.errors)


def test_duplicate_against_store():
    store = {"1": {"name": "Old", "email": "old@x.io"}}
    with pytest.raises(ImportRejected) as e:
        import_rows("id,name,email\n1,A,a@x.io\n", store)
    assert any(m.startswith("line 2") for m in e.value.errors) and store["1"]["name"] == "Old"


def test_missing_column():
    with pytest.raises(ImportRejected):
        import_rows("id,name\n1,A\n", {})


@pytest.mark.parametrize("email", ["nobody", "a@@b.io", "@b.io", "a@"])
def test_bad_email(email):
    with pytest.raises(ImportRejected):
        import_rows(f"id,name,email\n1,A,{email}\n", {})


def test_column_order_extra_columns_and_whitespace():
    store = {}
    assert import_rows("email,team,id,name\n a@x.io ,red, 7 , Ana \n", store) == {"imported": 1}
    assert store == {"7": {"name": "Ana", "email": "a@x.io"}}


def test_header_only():
    store = {}
    assert import_rows("id,name,email\n", store) == {"imported": 0} and store == {}


def test_one_error_per_bad_row():
    with pytest.raises(ImportRejected) as e:
        import_rows("id,name,email\n1,,x\n2,B,b@x.io\n2,C,c@x.io\n", {})
    lines = sorted({m.split(":")[0] for m in e.value.errors})
    assert lines == ["line 2", "line 4"]
