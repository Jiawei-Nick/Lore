import logging
import re

import sqlglot
import sqlglot.expressions as exp

from lore.models import Migration, MigrationFormat, Operation, SchemaChange
from lore.parsers.base import ParserPlugin
from lore.parsers.detector import detect_format

_log = logging.getLogger(__name__)

_FILE_HEADER = re.compile(r"^\+\+\+ b/(.+\.sql)$", re.MULTILINE)
_ADDED_LINE = re.compile(r"^\+(?!\+\+)(.+)$", re.MULTILINE)


def _parse_statement(sql: str) -> SchemaChange | None:
    sql = sql.strip()
    if not sql:
        return None
    # Remove leading SQL comments that can interfere with parsing
    # Find the first SQL statement keyword and take from there
    match = re.search(r'\b(ALTER\s+TABLE|CREATE\s+TABLE|DROP\s+TABLE|INSERT|UPDATE|DELETE)\b', sql, flags=re.IGNORECASE)
    if match:
        sql = sql[match.start():]
    if not sql:
        return None
    try:
        # Try parsing with MySQL dialect first (supports MODIFY COLUMN)
        statements = sqlglot.parse(sql, dialect='mysql')
        if not statements or statements[0] is None:
            # Fall back to default dialect
            statements = sqlglot.parse(sql)
        if not statements:
            return None
        stmt = statements[0]
    except Exception as exc:
        _log.debug("sqlglot failed to parse: %s — %s", sql[:120], exc)
        return None

    if isinstance(stmt, exp.Alter):
        table = stmt.find(exp.Table)
        table_name = table.name if table else "unknown"
        for action in stmt.args.get("actions", []):
            if isinstance(action, exp.ColumnDef):
                # ADD COLUMN — ColumnDef is the action directly
                dtype = action.find(exp.DataType)
                return SchemaChange(
                    operation=Operation.ADD,
                    table=table_name,
                    column=action.name,
                    data_type=dtype.sql() if dtype else None,
                    raw_sql=sql,
                )
            elif isinstance(action, exp.Drop) and action.args.get("kind", "").upper() == "COLUMN":
                col = action.args.get("this")
                return SchemaChange(
                    operation=Operation.DROP,
                    table=table_name,
                    column=col.name if col and hasattr(col, "name") else None,
                    raw_sql=sql,
                )
            elif isinstance(action, exp.AlterColumn):
                return SchemaChange(
                    operation=Operation.ALTER,
                    table=table_name,
                    column=action.name,
                    raw_sql=sql,
                )
            elif hasattr(exp, 'ModifyColumn') and isinstance(action, exp.ModifyColumn):
                # MySQL MODIFY COLUMN — contains a ColumnDef inside
                col_def = action.args.get("this")
                dtype = col_def.find(exp.DataType) if col_def else None
                return SchemaChange(
                    operation=Operation.ALTER,
                    table=table_name,
                    column=col_def.name if col_def and hasattr(col_def, "name") else None,
                    data_type=dtype.sql() if dtype else None,
                    raw_sql=sql,
                )
        return SchemaChange(operation=Operation.ALTER, table=table_name, raw_sql=sql)

    if isinstance(stmt, exp.Create):
        table = stmt.find(exp.Table)
        return SchemaChange(
            operation=Operation.CREATE,
            table=table.name if table else "unknown",
            raw_sql=sql,
        )

    if isinstance(stmt, exp.Drop):
        table = stmt.find(exp.Table)
        return SchemaChange(
            operation=Operation.DROP_TABLE,
            table=table.name if table else "unknown",
            raw_sql=sql,
        )

    return None


class FlywayParser(ParserPlugin):
    def parse(self, raw_diff: str) -> list[Migration]:
        migrations: list[Migration] = []
        file_blocks = _FILE_HEADER.split(raw_diff)

        it = iter(file_blocks[1:])
        for filepath, content in zip(it, it):
            filename = filepath.split("/")[-1]
            fmt = detect_format(filename, content)
            if fmt != MigrationFormat.FLYWAY:
                continue

            added_sql = " ".join(_ADDED_LINE.findall(content))
            statements = [s.strip() for s in added_sql.split(";") if s.strip()]
            changes = [c for s in statements if (c := _parse_statement(s + ";")) is not None]

            if changes:
                migrations.append(Migration(file=filepath, format=MigrationFormat.FLYWAY, changes=changes))

        return migrations
