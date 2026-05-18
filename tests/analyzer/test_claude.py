from unittest.mock import MagicMock, patch
from lore.models import Migration, SchemaChange, PipelineContext, Operation, RiskLevel
from lore.analyzer.claude import ClaudeAnalyzer


def _make_context_with_changes(operations: list[Operation]) -> PipelineContext:
    changes = [
        SchemaChange(operation=op, table="user", column="col", raw_sql=f"{op} col")
        for op in operations
    ]
    migration = Migration(file="V1__test.sql", format="flyway", changes=changes)
    ctx = PipelineContext(repo_path="/repo", branch="feature/test")
    ctx.migrations = [migration]
    return ctx


def test_selects_haiku_for_small_diff():
    analyzer = ClaudeAnalyzer(api_key="test")
    ctx = _make_context_with_changes([Operation.ADD, Operation.ADD])
    assert analyzer._select_model(ctx.migrations) == "claude-haiku-4-5-20251001"


def test_selects_sonnet_for_large_diff():
    analyzer = ClaudeAnalyzer(api_key="test")
    ctx = _make_context_with_changes([Operation.ADD] * 6)
    assert analyzer._select_model(ctx.migrations) == "claude-sonnet-4-6"


def test_selects_sonnet_for_breaking_change():
    analyzer = ClaudeAnalyzer(api_key="test")
    ctx = _make_context_with_changes([Operation.DROP])
    assert analyzer._select_model(ctx.migrations) == "claude-sonnet-4-6"


def test_selects_sonnet_for_drop_table():
    analyzer = ClaudeAnalyzer(api_key="test")
    ctx = _make_context_with_changes([Operation.DROP_TABLE])
    assert analyzer._select_model(ctx.migrations) == "claude-sonnet-4-6"


def test_selects_sonnet_for_alter():
    analyzer = ClaudeAnalyzer(api_key="test")
    ctx = _make_context_with_changes([Operation.ALTER])
    assert analyzer._select_model(ctx.migrations) == "claude-sonnet-4-6"


@patch("lore.analyzer.claude.anthropic.Anthropic")
def test_run_populates_analysis(mock_anthropic_class):
    mock_client = MagicMock()
    mock_anthropic_class.return_value = mock_client
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text='{"summary":"Added phone column","changes":[],"risk_level":"LOW","impact":["Profile API"],"reviewer_notes":"Low risk"}')]
    )

    analyzer = ClaudeAnalyzer(api_key="test")
    ctx = _make_context_with_changes([Operation.ADD])
    result = analyzer.run(ctx)

    assert result.analysis is not None
    assert result.analysis.risk_level == RiskLevel.LOW
    assert result.analysis.summary == "Added phone column"
    assert "Profile API" in result.analysis.impact
