from unittest.mock import MagicMock, patch
from datetime import date
from lore.models import PipelineContext, AnalysisReport, SchemaChange, Operation, RiskLevel
from lore.outputs.lark import LarkWikiOutput


def _make_context_with_report() -> PipelineContext:
    ctx = PipelineContext(repo_path="/repo", branch="feature/add-phone")
    ctx.analysis = AnalysisReport(
        summary="Added phone column to user table.",
        changes=[SchemaChange(operation=Operation.ADD, table="user", column="phone", data_type="VARCHAR(20)", raw_sql="ALTER TABLE user ADD COLUMN phone VARCHAR(20);")],
        risk_level=RiskLevel.LOW,
        impact=["User registration flow", "Profile API"],
        reviewer_notes="Low risk. Consider adding NOT NULL with a default.",
    )
    return ctx


def test_builds_page_title():
    output = LarkWikiOutput(app_id="x", app_secret="x", wiki_space_id="x", parent_node_token="x")
    ctx = _make_context_with_report()
    title = output._build_title(ctx, date(2026, 5, 17))
    assert title == "2026-05-17 | feature/add-phone | LOW"


def test_builds_page_content():
    output = LarkWikiOutput(app_id="x", app_secret="x", wiki_space_id="x", parent_node_token="x")
    ctx = _make_context_with_report()
    content = output._build_content(ctx, date(2026, 5, 17))
    assert "feature/add-phone" in content
    assert "LOW" in content
    assert "Added phone column" in content
    assert "user" in content
    assert "ADD" in content
    assert "Profile API" in content


@patch("lore.outputs.lark.httpx.post")
def test_run_calls_lark_api_and_sets_output_url(mock_post):
    mock_token_response = MagicMock()
    mock_token_response.json.return_value = {"tenant_access_token": "tok123"}
    mock_token_response.raise_for_status = MagicMock()

    mock_page_response = MagicMock()
    mock_page_response.json.return_value = {"data": {"node": {"node_token": "page-abc", "url": "https://lark.example/page-abc"}}}
    mock_page_response.raise_for_status = MagicMock()

    mock_post.side_effect = [mock_token_response, mock_page_response]

    output = LarkWikiOutput(app_id="app1", app_secret="sec1", wiki_space_id="space1", parent_node_token="parent1")
    ctx = _make_context_with_report()
    result = output.run(ctx)

    assert result.output_url == "https://lark.example/page-abc"
    assert mock_post.call_count == 2
