from lore.parsers.liquibase import LiquibaseParser
from lore.models import Operation, MigrationFormat


def test_parses_liquibase_xml_add_column():
    xml_content = """
<databaseChangeLog>
  <changeSet id="1" author="dev">
    <addColumn tableName="user">
      <column name="phone" type="VARCHAR(20)"/>
    </addColumn>
  </changeSet>
</databaseChangeLog>
"""
    diff = "+++ b/db/changelog.xml\n" + "\n".join(f"+{line}" for line in xml_content.splitlines())
    parser = LiquibaseParser()
    migrations = parser.parse(diff)
    assert len(migrations) == 1
    assert migrations[0].format == MigrationFormat.LIQUIBASE
    assert migrations[0].changes[0].operation == Operation.ADD
    assert migrations[0].changes[0].table == "user"
    assert migrations[0].changes[0].column == "phone"


def test_parses_liquibase_drop_column():
    xml_content = """
<databaseChangeLog>
  <changeSet id="2" author="dev">
    <dropColumn tableName="orders" columnName="legacy_ref"/>
  </changeSet>
</databaseChangeLog>
"""
    diff = "+++ b/db/changelog.xml\n" + "\n".join(f"+{line}" for line in xml_content.splitlines())
    parser = LiquibaseParser()
    migrations = parser.parse(diff)
    assert migrations[0].changes[0].operation == Operation.DROP
    assert migrations[0].changes[0].column == "legacy_ref"


def test_ignores_non_liquibase_files():
    diff = "+++ b/README.md\n+Some text\n"
    parser = LiquibaseParser()
    assert parser.parse(diff) == []


def test_parses_liquibase_create_table():
    xml_content = """
<databaseChangeLog>
  <changeSet id="3" author="dev">
    <createTable tableName="payments">
      <column name="id" type="BIGINT"/>
    </createTable>
  </changeSet>
</databaseChangeLog>
"""
    diff = "+++ b/db/changelog.xml\n" + "\n".join(f"+{line}" for line in xml_content.splitlines())
    parser = LiquibaseParser()
    migrations = parser.parse(diff)
    assert len(migrations) == 1
    assert migrations[0].changes[0].operation == Operation.CREATE
    assert migrations[0].changes[0].table == "payments"


def test_parses_liquibase_drop_table():
    xml_content = """
<databaseChangeLog>
  <changeSet id="4" author="dev">
    <dropTable tableName="legacy_data"/>
  </changeSet>
</databaseChangeLog>
"""
    diff = "+++ b/db/changelog.xml\n" + "\n".join(f"+{line}" for line in xml_content.splitlines())
    parser = LiquibaseParser()
    migrations = parser.parse(diff)
    assert len(migrations) == 1
    assert migrations[0].changes[0].operation == Operation.DROP_TABLE
    assert migrations[0].changes[0].table == "legacy_data"
