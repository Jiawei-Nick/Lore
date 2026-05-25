import os
from typer.testing import CliRunner
from unittest.mock import patch, MagicMock
from dotenv import load_dotenv
from lore.cli import app

load_dotenv()

runner = CliRunner()

_LORE_YAML = f"""
aws:
  access_key_id: {os.getenv("AWS_ACCESS_KEY_ID", "test-key")}
  secret_access_key: {os.getenv("AWS_SECRET_ACCESS_KEY", "test-secret")}
  region: {os.getenv("AWS_REGION", "ap-southeast-1")}
lark:
  app_id: {os.getenv("LARK_APP_ID", "app1")}
  app_secret: {os.getenv("LARK_APP_SECRET", "sec1")}
  folder_token: {os.getenv("LARK_FOLDER_TOKEN", "folder1")}
  parent_doc_id: {os.getenv("LARK_PARENT_DOC_ID", "parent1")}
repo:
  default_path: ./
  default_branch: main
"""


def test_analyze_prints_success(tmp_path):
    (tmp_path / "lore.yaml").write_text(_LORE_YAML)

    with patch("lore.cli.Pipeline") as mock_pipeline_cls, \
         patch("lore.cli.GitLocalSource"), \
         patch("lore.cli.CompositeParser"), \
         patch("lore.cli.ClaudeAnalyzer"), \
         patch("lore.cli.LarkDocOutput"), \
         patch("lore.cli.SchemaStore"):

        mock_pipeline = MagicMock()
        mock_pipeline_cls.return_value = mock_pipeline
        mock_ctx = MagicMock()
        mock_ctx.analysis.risk_level.value = "LOW"
        mock_ctx.analysis.summary = "Added phone column."
        mock_ctx.output_url = "https://lark.example/docx/page-1"
        mock_ctx.migrations = [MagicMock()]
        mock_pipeline.run.return_value = mock_ctx

        result = runner.invoke(app, [
            "analyze",
            "--repo", str(tmp_path),
            "--branch", "feature/test",
            "--config", str(tmp_path / "lore.yaml"),
        ])

    assert result.exit_code == 0, result.output
    assert "LOW" in result.output
    assert "lark.example" in result.output


def test_analyze_exits_cleanly_when_no_migrations(tmp_path):
    (tmp_path / "lore.yaml").write_text(_LORE_YAML)

    with patch("lore.cli.Pipeline") as mock_pipeline_cls, \
         patch("lore.cli.GitLocalSource"), \
         patch("lore.cli.CompositeParser"), \
         patch("lore.cli.ClaudeAnalyzer"), \
         patch("lore.cli.LarkDocOutput"), \
         patch("lore.cli.SchemaStore"):

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

    assert result.exit_code == 0, result.output
    assert "No DB migration" in result.output


def test_init_command_creates_schema_and_updates_erd(tmp_path):
    (tmp_path / "lore.yaml").write_text(_LORE_YAML)

    with patch("lore.cli.introspect_database") as mock_introspect, \
         patch("lore.cli.LarkDocOutput") as mock_lark_cls:

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
