import re

from lore.models import MigrationFormat


def detect_format(filename: str, content: str) -> MigrationFormat:
    """Detect migration format from filename and/or content."""
    if re.match(r"V\d+__.*\.sql$", filename.split("/")[-1]):
        return MigrationFormat.FLYWAY
    if "databaseChangeLog" in content:
        return MigrationFormat.LIQUIBASE
    if filename.endswith(".xml") and "changeSet" in content:
        return MigrationFormat.LIQUIBASE
    if filename.endswith((".yaml", ".yml")) and "changeSet" in content:
        return MigrationFormat.LIQUIBASE
    return MigrationFormat.RAW_DDL
