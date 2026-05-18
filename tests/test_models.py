# tests/test_models.py
from lore.models import (
    SchemaChange, Migration, AnalysisReport, PipelineContext,
    Operation, MigrationFormat, RiskLevel,
)


def test_schema_change_optional_fields_default_to_none_and_empty():
    change = SchemaChange(operation=Operation.ADD, table="user")
    assert change.column is None
    assert change.data_type is None
    assert change.raw_sql == ""


def test_migration_holds_changes():
    change = SchemaChange(operation=Operation.ADD, table="user", column="phone", data_type="VARCHAR(20)")
    migration = Migration(file="V1__add_phone.sql", format=MigrationFormat.FLYWAY, changes=[change])
    assert len(migration.changes) == 1
    assert migration.format == MigrationFormat.FLYWAY


def test_pipeline_context_defaults():
    ctx = PipelineContext(repo_path="/repo", branch="main")
    assert ctx.raw_diff == ""
    assert ctx.migrations == []
    assert ctx.analysis is None
    assert ctx.output_url is None
    assert ctx.base == "main"


def test_analysis_report_construction():
    change = SchemaChange(operation=Operation.ADD, table="user", column="phone", data_type="VARCHAR(20)")
    report = AnalysisReport(
        summary="Added phone column",
        changes=[change],
        risk_level=RiskLevel.LOW,
        impact=["Profile API"],
        reviewer_notes="Low risk",
    )
    assert report.risk_level == RiskLevel.LOW
    assert report.risk_level == "LOW"  # str, Enum — still equal to plain string


def test_enum_values_are_strings():
    assert Operation.ADD == "ADD"
    assert MigrationFormat.FLYWAY == "flyway"
    assert RiskLevel.HIGH == "HIGH"
