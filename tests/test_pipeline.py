from unittest.mock import MagicMock
from lore.models import PipelineContext, Migration, SchemaChange, AnalysisReport, Operation, MigrationFormat, RiskLevel
from lore.pipeline import Pipeline


def _make_mock_source():
    source = MagicMock()
    def run(ctx):
        ctx.raw_diff = "+++ b/db/V1__test.sql\n+ALTER TABLE user ADD COLUMN phone VARCHAR(20);\n"
        return ctx
    source.run.side_effect = run
    return source


def _make_mock_parser():
    parser = MagicMock()
    def run(ctx):
        ctx.migrations = [Migration(
            file="V1__test.sql",
            format=MigrationFormat.FLYWAY,
            changes=[SchemaChange(operation=Operation.ADD, table="user", column="phone", data_type="VARCHAR(20)", raw_sql="")]
        )]
        return ctx
    parser.run.side_effect = run
    return parser


def _make_mock_analyzer():
    analyzer = MagicMock()
    def run(ctx):
        ctx.analysis = AnalysisReport(
            summary="Added phone",
            changes=ctx.migrations[0].changes,
            risk_level=RiskLevel.LOW,
            impact=["Profile API"],
            reviewer_notes="OK",
        )
        return ctx
    analyzer.run.side_effect = run
    return analyzer


def _make_mock_output():
    output = MagicMock()
    def run(ctx):
        ctx.output_url = "https://lark.example/page-1"
        return ctx
    output.run.side_effect = run
    return output


def test_pipeline_runs_all_stages():
    source = _make_mock_source()
    parser = _make_mock_parser()
    analyzer = _make_mock_analyzer()
    output = _make_mock_output()

    pipeline = Pipeline(source=source, parser=parser, analyzer=analyzer, output=output)
    ctx = PipelineContext(repo_path="/repo", branch="feature/test")
    result = pipeline.run(ctx)

    assert result.raw_diff != ""
    assert len(result.migrations) == 1
    assert result.analysis is not None
    assert result.analysis.risk_level == RiskLevel.LOW
    assert result.output_url == "https://lark.example/page-1"


def test_pipeline_skips_analysis_when_no_migrations():
    source = MagicMock()
    def run_empty(ctx):
        ctx.raw_diff = "+++ b/README.md\n+some text\n"
        return ctx
    source.run.side_effect = run_empty

    parser = MagicMock()
    def run_no_migrations(ctx):
        ctx.migrations = []
        return ctx
    parser.run.side_effect = run_no_migrations

    analyzer = MagicMock()
    output = MagicMock()

    pipeline = Pipeline(source=source, parser=parser, analyzer=analyzer, output=output)
    ctx = PipelineContext(repo_path="/repo", branch="main")
    result = pipeline.run(ctx)

    analyzer.run.assert_not_called()
    output.run.assert_not_called()
    assert result.analysis is None


def test_pipeline_updates_schema_store_after_run(tmp_path):
    from lore.schema_store import SchemaStore
    from lore.models import Migration, SchemaChange, AnalysisReport, Operation, MigrationFormat, RiskLevel

    store = SchemaStore(path=str(tmp_path / "lore-schema.json"))
    store.load()

    source = MagicMock()
    def run_source(ctx):
        ctx.raw_diff = ""
        return ctx
    source.run.side_effect = run_source

    parser = MagicMock()
    def run_parser(ctx):
        ctx.migrations = [Migration(
            file="V1__test.sql",
            format=MigrationFormat.FLYWAY,
            changes=[SchemaChange(operation=Operation.ADD, table="user", column="email", data_type="VARCHAR(255)", raw_sql="")]
        )]
        return ctx
    parser.run.side_effect = run_parser

    analyzer = MagicMock()
    def run_analyzer(ctx):
        ctx.analysis = AnalysisReport(summary="", changes=ctx.migrations[0].changes, risk_level=RiskLevel.LOW, impact=[], reviewer_notes="")
        return ctx
    analyzer.run.side_effect = run_analyzer

    output = MagicMock()
    def run_output(ctx):
        ctx.output_url = "https://lark.example/page-1"
        return ctx
    output.run.side_effect = run_output

    pipeline = Pipeline(source=source, parser=parser, analyzer=analyzer, output=output, schema_store=store)
    ctx = PipelineContext(repo_path="/repo", branch="feature/test")
    pipeline.run(ctx)

    assert "user" in store.tables
    assert "email" in store.tables["user"]["columns"]
