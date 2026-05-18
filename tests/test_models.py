from lore.models import SchemaChange, Migration, AnalysisReport, PipelineContext

def test_schema_change_defaults():
    change = SchemaChange(
        operation="ADD",
        table="user",
        column="phone",
        data_type="VARCHAR(20)",
        raw_sql="ALTER TABLE user ADD COLUMN phone VARCHAR(20);",
    )
    assert change.operation == "ADD"
    assert change.column == "phone"

def test_migration_holds_changes():
    change = SchemaChange(operation="ADD", table="user", column="phone", data_type="VARCHAR(20)", raw_sql="")
    migration = Migration(file="V1__add_phone.sql", format="flyway", changes=[change])
    assert len(migration.changes) == 1

def test_pipeline_context_defaults():
    ctx = PipelineContext(repo_path="/repo", branch="main")
    assert ctx.raw_diff == ""
    assert ctx.migrations == []
    assert ctx.analysis is None
    assert ctx.output_url is None
