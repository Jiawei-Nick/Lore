# lore/models.py
from dataclasses import dataclass, field
from enum import Enum


class Operation(str, Enum):
    ADD = "ADD"
    DROP = "DROP"
    ALTER = "ALTER"
    CREATE = "CREATE"
    DROP_TABLE = "DROP_TABLE"


class MigrationFormat(str, Enum):
    FLYWAY = "flyway"
    LIQUIBASE = "liquibase"
    RAW_DDL = "raw_ddl"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


@dataclass
class SchemaChange:
    operation: Operation
    table: str
    column: str | None = None
    data_type: str | None = None
    raw_sql: str = ""


@dataclass
class Migration:
    file: str
    format: MigrationFormat
    changes: list[SchemaChange] = field(default_factory=list)


@dataclass
class AnalysisReport:
    summary: str
    changes: list[SchemaChange]
    risk_level: RiskLevel
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
