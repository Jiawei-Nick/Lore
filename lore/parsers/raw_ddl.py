import re
from lore.models import Migration, MigrationFormat
from lore.parsers.base import ParserPlugin
from lore.parsers.detector import detect_format
from lore.parsers.flyway import _FILE_HEADER, _ADDED_LINE, _parse_statement

_FLYWAY_PATTERN = re.compile(r"V\d+__.*\.sql$")


class RawDDLParser(ParserPlugin):
    def parse(self, raw_diff: str) -> list[Migration]:
        migrations: list[Migration] = []
        file_blocks = _FILE_HEADER.split(raw_diff)

        it = iter(file_blocks[1:])
        for filepath, content in zip(it, it):
            filename = filepath.split("/")[-1]
            if _FLYWAY_PATTERN.match(filename):
                continue  # handled by FlywayParser
            added_sql = " ".join(_ADDED_LINE.findall(content))
            fmt = detect_format(filename, added_sql)
            if fmt != MigrationFormat.RAW_DDL:
                continue

            statements = [s.strip() for s in added_sql.split(";") if s.strip()]
            changes = [c for s in statements if (c := _parse_statement(s + ";")) is not None]

            if changes:
                migrations.append(Migration(file=filepath, format=MigrationFormat.RAW_DDL, changes=changes))

        return migrations
