from lore.models import Migration
from lore.parsers.base import ParserPlugin
from lore.parsers.flyway import FlywayParser
from lore.parsers.liquibase import LiquibaseParser
from lore.parsers.raw_ddl import RawDDLParser


class CompositeParser(ParserPlugin):
    def __init__(self) -> None:
        self._parsers = [FlywayParser(), LiquibaseParser(), RawDDLParser()]

    def parse(self, raw_diff: str) -> list[Migration]:
        results: list[Migration] = []
        for parser in self._parsers:
            results.extend(parser.parse(raw_diff))
        return results
    # run() inherited from ParserPlugin — calls self.parse()
