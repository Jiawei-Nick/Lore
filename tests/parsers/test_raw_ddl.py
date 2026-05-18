from lore.parsers.raw_ddl import RawDDLParser
from lore.models import Operation, MigrationFormat


def test_parses_raw_create_table():
    sql = "CREATE TABLE payments (id BIGINT PRIMARY KEY, amount DECIMAL(10,2));"
    diff = f"+++ b/schema/init.sql\n@@ -0,0 +1 @@\n+{sql}\n"
    parser = RawDDLParser()
    migrations = parser.parse(diff)
    assert len(migrations) == 1
    assert migrations[0].format == MigrationFormat.RAW_DDL
    assert migrations[0].changes[0].operation == Operation.CREATE
    assert migrations[0].changes[0].table == "payments"


def test_ignores_flyway_files():
    diff = "+++ b/db/V1__init.sql\n+CREATE TABLE foo (id INT);\n"
    parser = RawDDLParser()
    assert parser.parse(diff) == []
