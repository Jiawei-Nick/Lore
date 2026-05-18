from lore.parsers.composite import CompositeParser
from lore.models import MigrationFormat


def test_composite_detects_flyway():
    diff = "+++ b/db/V1__add_phone.sql\n@@ -0,0 +1 @@\n+ALTER TABLE user ADD COLUMN phone VARCHAR(20);\n"
    parser = CompositeParser()
    migrations = parser.parse(diff)
    assert len(migrations) == 1
    assert migrations[0].format == MigrationFormat.FLYWAY


def test_composite_detects_raw_ddl():
    diff = "+++ b/schema/init.sql\n@@ -0,0 +1 @@\n+CREATE TABLE payments (id BIGINT PRIMARY KEY);\n"
    parser = CompositeParser()
    migrations = parser.parse(diff)
    assert len(migrations) == 1
    assert migrations[0].format == MigrationFormat.RAW_DDL


def test_composite_returns_empty_for_no_sql_files():
    diff = "+++ b/src/App.java\n@@ -0,0 +1 @@\n+public class App {}\n"
    parser = CompositeParser()
    assert parser.parse(diff) == []
