from lore.models import MigrationFormat, Operation, SchemaChange
from lore.parsers.flyway import FlywayParser


def test_parses_add_column():
    sql = "ALTER TABLE user ADD COLUMN phone VARCHAR(20);"
    diff = f"+++ b/db/migrations/V2__add_phone.sql\n@@ -0,0 +1 @@\n+{sql}\n"
    parser = FlywayParser()
    migrations = parser.parse(diff)
    assert len(migrations) == 1
    assert migrations[0].format == MigrationFormat.FLYWAY
    assert migrations[0].file == "db/migrations/V2__add_phone.sql"
    changes = migrations[0].changes
    assert len(changes) == 1
    assert changes[0].operation == Operation.ADD
    assert changes[0].table == "user"
    assert changes[0].column == "phone"
    assert changes[0].data_type == "VARCHAR(20)"


def test_parses_create_table():
    sql = "CREATE TABLE orders (id BIGINT PRIMARY KEY, user_id BIGINT NOT NULL);"
    diff = f"+++ b/db/V1__create_orders.sql\n@@ -0,0 +1 @@\n+{sql}\n"
    parser = FlywayParser()
    migrations = parser.parse(diff)
    assert len(migrations) == 1
    assert migrations[0].changes[0].operation == Operation.CREATE
    assert migrations[0].changes[0].table == "orders"


def test_parses_drop_column():
    sql = "ALTER TABLE user DROP COLUMN legacy_field;"
    diff = f"+++ b/db/V3__drop_legacy.sql\n@@ -0,0 +1 @@\n+{sql}\n"
    parser = FlywayParser()
    migrations = parser.parse(diff)
    assert migrations[0].changes[0].operation == Operation.DROP
    assert migrations[0].changes[0].column == "legacy_field"


def test_ignores_non_migration_files():
    diff = "+++ b/src/main/java/UserService.java\n@@ -0,0 +1 @@\n+public class UserService {}\n"
    parser = FlywayParser()
    migrations = parser.parse(diff)
    assert migrations == []
