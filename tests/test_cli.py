from typer.testing import CliRunner
from unittest.mock import patch, MagicMock
from lore.cli import app

runner = CliRunner()


def test_analyze_prints_success(tmp_path):
    (tmp_path / "lore.yaml").write_text("""
anthropic:
  api_key: test-key
lark:
  app_id: app1
  app_secret: sec1
  wiki_space_id: space1
  parent_node_token: parent1
repo:
  default_path: ./
  default_branch: main
""")

    with patch("lore.cli.Pipeline") as mock_pipeline_cls, \
         patch("lore.cli.GitLocalSource"), \
         patch("lore.cli.CompositeParser"), \
         patch("lore.cli.ClaudeAnalyzer"), \
         patch("lore.cli.LarkWikiOutput"):

        mock_pipeline = MagicMock()
        mock_pipeline_cls.return_value = mock_pipeline
        mock_ctx = MagicMock()
        mock_ctx.analysis.risk_level.value = "LOW"
        mock_ctx.analysis.summary = "Added phone column."
        mock_ctx.output_url = "https://lark.example/page-1"
        mock_ctx.migrations = [MagicMock()]
        mock_pipeline.run.return_value = mock_ctx

        result = runner.invoke(app, [
            "analyze",
            "--repo", str(tmp_path),
            "--branch", "feature/test",
            "--config", str(tmp_path / "lore.yaml"),
        ])

    assert result.exit_code == 0
    assert "LOW" in result.output
    assert "lark.example" in result.output


def test_analyze_exits_cleanly_when_no_migrations(tmp_path):
    (tmp_path / "lore.yaml").write_text("""
anthropic:
  api_key: test-key
lark:
  app_id: app1
  app_secret: sec1
  wiki_space_id: space1
  parent_node_token: parent1
repo:
  default_path: ./
  default_branch: main
""")
    with patch("lore.cli.Pipeline") as mock_pipeline_cls, \
         patch("lore.cli.GitLocalSource"), \
         patch("lore.cli.CompositeParser"), \
         patch("lore.cli.ClaudeAnalyzer"), \
         patch("lore.cli.LarkWikiOutput"):

        mock_pipeline = MagicMock()
        mock_pipeline_cls.return_value = mock_pipeline
        mock_ctx = MagicMock()
        mock_ctx.migrations = []
        mock_ctx.analysis = None
        mock_pipeline.run.return_value = mock_ctx

        result = runner.invoke(app, [
            "analyze",
            "--repo", str(tmp_path),
            "--branch", "main",
            "--config", str(tmp_path / "lore.yaml"),
        ])

    assert result.exit_code == 0
    assert "No DB migration" in result.output


def test_init_command_creates_schema_and_updates_erd(tmp_path):
    (tmp_path / "lore.yaml").write_text("""
anthropic:
  api_key: test-key
lark:
  app_id: app1
  app_secret: sec1
  wiki_space_id: space1
  parent_node_token: parent1
repo:
  default_path: ./
  default_branch: main
""")
    with patch("lore.cli.introspect_postgres") as mock_introspect, \
         patch("lore.cli.LarkWikiOutput") as mock_lark_cls:

        mock_introspect.return_value = {
            "user": {"columns": {"id": {"type": "bigint", "nullable": False}}}
        }
        mock_lark = MagicMock()
        mock_lark_cls.return_value = mock_lark

        result = runner.invoke(app, [
            "init",
            "--db", "postgresql://user:pass@localhost/mydb",
            "--config", str(tmp_path / "lore.yaml"),
            "--schema-path", str(tmp_path / "lore-schema.json"),
        ])

    assert result.exit_code == 0, result.output
    assert "Schema snapshot saved" in result.output
    mock_lark.update_erd_page.assert_called_once()
