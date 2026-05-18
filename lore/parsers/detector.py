import re


def detect_format(filename: str, content: str) -> str:
    """Detect migration format from filename and/or content."""
    if re.match(r"V\d+__.*\.sql$", filename.split("/")[-1]):
        return "flyway"
    if "databaseChangeLog" in content:
        return "liquibase"
    if filename.endswith(".xml") and "changeSet" in content:
        return "liquibase"
    if filename.endswith((".yaml", ".yml")) and "changeSet" in content:
        return "liquibase"
    return "raw_ddl"
