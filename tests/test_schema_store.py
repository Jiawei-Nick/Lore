import pytest
from lore.models import SchemaChange, Operation
from lore.schema_store import SchemaStore


@pytest.fixture
def store(tmp_path):
    return SchemaStore(path=str(tmp_path / "lore-schema.json"))


def test_empty_store_has_no_tables(store):
    assert store.tables == {}


def test_apply_create_table(store):
    change = SchemaChange(operation=Operation.CREATE, table="user", raw_sql="CREATE TABLE user (id BIGINT);")
    store.apply([change])
    assert "user" in store.tables


def test_apply_add_column(store):
    store.apply([SchemaChange(operation=Operation.CREATE, table="user", raw_sql="")])
    store.apply([SchemaChange(operation=Operation.ADD, table="user", column="phone", data_type="VARCHAR(20)", raw_sql="")])
    assert store.tables["user"]["columns"]["phone"]["type"] == "VARCHAR(20)"


def test_apply_drop_column(store):
    store.apply([SchemaChange(operation=Operation.CREATE, table="user", raw_sql="")])
    store.apply([SchemaChange(operation=Operation.ADD, table="user", column="phone", data_type="VARCHAR(20)", raw_sql="")])
    store.apply([SchemaChange(operation=Operation.DROP, table="user", column="phone", raw_sql="")])
    assert "phone" not in store.tables["user"]["columns"]


def test_apply_drop_table(store):
    store.apply([SchemaChange(operation=Operation.CREATE, table="user", raw_sql="")])
    store.apply([SchemaChange(operation=Operation.DROP_TABLE, table="user", raw_sql="")])
    assert "user" not in store.tables


def test_save_and_load_roundtrip(store, tmp_path):
    store.apply([SchemaChange(operation=Operation.CREATE, table="orders", raw_sql="")])
    store.apply([SchemaChange(operation=Operation.ADD, table="orders", column="amount", data_type="DECIMAL(10,2)", raw_sql="")])
    store.save()

    store2 = SchemaStore(path=str(tmp_path / "lore-schema.json"))
    store2.load()
    assert "orders" in store2.tables
    assert store2.tables["orders"]["columns"]["amount"]["type"] == "DECIMAL(10,2)"
