from lore.models import MigrationFormat
from lore.parsers.detector import detect_format


def test_detects_flyway_by_filename():
    assert detect_format("V2__add_phone.sql", "") == MigrationFormat.FLYWAY
    assert detect_format("V10__create_orders_table.sql", "") == MigrationFormat.FLYWAY


def test_detects_liquibase_xml_by_content():
    content = '<databaseChangeLog xmlns="http://www.liquibase.org/xml/ns/dbchangelog">'
    assert detect_format("changelog.xml", content) == MigrationFormat.LIQUIBASE


def test_detects_liquibase_yaml_by_content():
    content = "databaseChangeLog:\n  - changeSet:"
    assert detect_format("changelog.yaml", content) == MigrationFormat.LIQUIBASE


def test_falls_back_to_raw_ddl():
    assert detect_format("schema.sql", "CREATE TABLE foo (id INT);") == MigrationFormat.RAW_DDL
