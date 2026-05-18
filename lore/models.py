from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class SchemaChange:
    operation: str        # ADD | DROP | ALTER | CREATE | DROP_TABLE
    table: str
    column: str | None = None
    data_type: str | None = None
    raw_sql: str = ""


@dataclass
class Migration:
    file: str             # e.g. V3__add_phone_column.sql
    format: str           # flyway | liquibase | raw_ddl
    changes: list[SchemaChange] = field(default_factory=list)


@dataclass
class AnalysisReport:
    summary: str
    changes: list[SchemaChange]
    risk_level: str       # LOW | MEDIUM | HIGH
    impact: list[str]
    reviewer_notes: str


@dataclass
class PipelineContext:
    repo_path: str
    branch: str
    base: str = "main"
    raw_diff: str = ""
    migrations: list[Migration] = field(default_factory=list)
    analysis: AnalysisReport | None = None
    output_url: str | None = None
