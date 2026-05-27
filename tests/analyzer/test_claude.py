import os
from unittest.mock import MagicMock, patch
from dotenv import load_dotenv
from lore.models import Migration, SchemaChange, PipelineContext, Operation, RiskLevel, MigrationFormat
from lore.analyzer.claude import ClaudeAnalyzer, _MODEL_HAIKU, _MODEL_SONNET

load_dotenv()

# Clear AWS_BEARER_TOKEN_BEDROCK to avoid conflicts with test credentials
if "AWS_BEARER_TOKEN_BEDROCK" in os.environ:
    del os.environ["AWS_BEARER_TOKEN_BEDROCK"]

_AWS_KEY = os.getenv("AWS_ACCESS_KEY_ID", "test-key")
_AWS_SECRET = os.getenv("AWS_SECRET_ACCESS_KEY", "test-secret")
_AWS_REGION = os.getenv("AWS_REGION", "ap-southeast-1")


def _make_analyzer():
    return ClaudeAnalyzer(
        aws_access_key_id=_AWS_KEY,
        aws_secret_access_key=_AWS_SECRET,
        aws_region=_AWS_REGION,
    )


def _make_context_with_changes(operations: list[Operation]) -> PipelineContext:
    changes = [
        SchemaChange(operation=op, table="user", column="col", raw_sql=f"{op} col")
        for op in operations
    ]
    migration = Migration(file="V1__test.sql", format=MigrationFormat.FLYWAY, changes=changes)
    ctx = PipelineContext(repo_path="/repo", branch="feature/test")
    ctx.migrations = [migration]
    return ctx


def test_selects_haiku_for_small_diff():
    ctx = _make_context_with_changes([Operation.ADD, Operation.ADD])
    assert _make_analyzer()._select_model(ctx.migrations) == _MODEL_HAIKU


def test_selects_sonnet_for_large_diff():
    ctx = _make_context_with_changes([Operation.ADD] * 6)
    assert _make_analyzer()._select_model(ctx.migrations) == _MODEL_SONNET


def test_selects_sonnet_for_breaking_change():
    ctx = _make_context_with_changes([Operation.DROP])
    assert _make_analyzer()._select_model(ctx.migrations) == _MODEL_SONNET


def test_selects_sonnet_for_drop_table():
    ctx = _make_context_with_changes([Operation.DROP_TABLE])
    assert _make_analyzer()._select_model(ctx.migrations) == _MODEL_SONNET


def test_selects_sonnet_for_alter():
    ctx = _make_context_with_changes([Operation.ALTER])
    assert _make_analyzer()._select_model(ctx.migrations) == _MODEL_SONNET


@patch("lore.analyzer.claude.AnthropicBedrock")
def test_run_populates_analysis(mock_bedrock_class):
    mock_client = MagicMock()
    mock_bedrock_class.return_value = mock_client
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text='{"summary":"Added phone column","changes":[],"risk_level":"LOW","impact":["Profile API"],"reviewer_notes":"Low risk"}')]
    )

    ctx = _make_context_with_changes([Operation.ADD])
    result = _make_analyzer().run(ctx)

    assert result.analysis is not None
    assert result.analysis.risk_level == RiskLevel.LOW
    assert result.analysis.summary == "Added phone column"
    assert "Profile API" in result.analysis.impact


@patch("lore.analyzer.claude.AnthropicBedrock")
def test_run_strips_markdown_fences(mock_bedrock_class):
    mock_client = MagicMock()
    mock_bedrock_class.return_value = mock_client
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text='```json\n{"summary":"ok","changes":[],"risk_level":"LOW","impact":[],"reviewer_notes":""}\n```')]
    )

    ctx = _make_context_with_changes([Operation.ADD])
    result = _make_analyzer().run(ctx)

    assert result.analysis.risk_level == RiskLevel.LOW
    assert result.analysis.summary == "ok"
