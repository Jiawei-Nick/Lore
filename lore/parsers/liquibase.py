import re
import xml.etree.ElementTree as ET
from lore.models import Migration, SchemaChange, MigrationFormat, Operation
from lore.parsers.base import ParserPlugin
from lore.parsers.detector import detect_format

_FILE_HEADER = re.compile(r"^\+\+\+ b/(.+)$", re.MULTILINE)
_ADDED_LINE = re.compile(r"^\+(?!\+\+)(.*)$", re.MULTILINE)


def _parse_xml_changeset(xml_text: str) -> list[SchemaChange]:
    changes: list[SchemaChange] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
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
                changes.append(SchemaChange(
                    operation=Operation.DROP,
                    table=child.get("tableName", "unknown"),
                    column=child.get("columnName"),
                    raw_sql=f"dropColumn {child.get('tableName')}.{child.get('columnName')}",
                ))
            elif child_tag == "createTable":
                changes.append(SchemaChange(
                    operation=Operation.CREATE,
                    table=child.get("tableName", "unknown"),
                    raw_sql=f"createTable {child.get('tableName')}",
                ))
            elif child_tag == "dropTable":
                changes.append(SchemaChange(
                    operation=Operation.DROP_TABLE,
                    table=child.get("tableName", "unknown"),
                    raw_sql=f"dropTable {child.get('tableName')}",
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
