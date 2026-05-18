import logging
import re
import xml.etree.ElementTree as ET
from lore.models import Migration, SchemaChange, MigrationFormat, Operation
from lore.parsers.base import ParserPlugin
from lore.parsers.detector import detect_format

_log = logging.getLogger(__name__)

_FILE_HEADER = re.compile(r"^\+\+\+ b/(.+\.(?:xml|yaml|yml))$", re.MULTILINE)
_ADDED_LINE = re.compile(r"^\+(?!\+\+)(.*)$", re.MULTILINE)


def _parse_xml_changeset(xml_text: str) -> list[SchemaChange]:
    changes: list[SchemaChange] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        _log.warning("Failed to parse Liquibase XML: %s", exc)
        return changes

    for changeset in root.iter():
        tag = changeset.tag.split("}")[-1] if "}" in changeset.tag else changeset.tag
        if tag != "changeSet":
            continue
        for child in changeset:
            child_tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if child_tag == "addColumn":
                table = child.get("tableName", "unknown")
                for col in child:
                    col_tag = col.tag.split("}")[-1] if "}" in col.tag else col.tag
                    if col_tag == "column":
                        changes.append(SchemaChange(
                            operation=Operation.ADD,
                            table=table,
                            column=col.get("name"),
                            data_type=col.get("type"),
                            raw_sql=f"addColumn {table}.{col.get('name')}",
                        ))
            elif child_tag == "dropColumn":
                table = child.get("tableName") or "unknown"
                col = child.get("columnName") or "unknown"
                changes.append(SchemaChange(
                    operation=Operation.DROP,
                    table=table,
                    column=child.get("columnName"),
                    raw_sql=f"dropColumn {table}.{col}",
                ))
            elif child_tag == "createTable":
                table = child.get("tableName") or "unknown"
                changes.append(SchemaChange(
                    operation=Operation.CREATE,
                    table=table,
                    raw_sql=f"createTable {table}",
                ))
            elif child_tag == "dropTable":
                table = child.get("tableName") or "unknown"
                changes.append(SchemaChange(
                    operation=Operation.DROP_TABLE,
                    table=table,
                    raw_sql=f"dropTable {table}",
                ))
    return changes


class LiquibaseParser(ParserPlugin):
    def parse(self, raw_diff: str) -> list[Migration]:
        migrations: list[Migration] = []
        file_blocks = _FILE_HEADER.split(raw_diff)

        it = iter(file_blocks[1:])
        for filepath, content in zip(it, it):
            filename = filepath.split("/")[-1]
            added_lines = "\n".join(_ADDED_LINE.findall(content))
            fmt = detect_format(filename, added_lines)
            if fmt != MigrationFormat.LIQUIBASE:
                continue

            changes = _parse_xml_changeset(added_lines)
            if changes:
                migrations.append(Migration(file=filepath, format=MigrationFormat.LIQUIBASE, changes=changes))

        return migrations
