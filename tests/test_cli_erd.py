from unittest.mock import patch, MagicMock
from typer.testing import CliRunner
from lore.cli import app
from lore.models import Migration, MigrationFormat, SchemaChange, Operation, RiskLevel

runner = CliRunner()


def _make_cfg():
    return MagicMock(
        lark_app_id="id", lark_app_secret="sec",
        lark_folder_token="folder", lark_parent_doc_id="parent_doc_123",
        aws_region="ap-southeast-1", aws_access_key_id="key",
        aws_secret_access_key="secret", aws_session_token=None,
    )


def _make_pipeline_result():
    ctx = MagicMock()
    ctx.migrations = [
        Migration(
            file="V1__add_phone.sql",
            format=MigrationFormat.FLYWAY,
            changes=[SchemaChange(operation=Operation.ADD, table="user", column="phone")],
        )
    ]
    ctx.output_url = "https://open.larksuite.com/docx/sub_doc_789"
    ctx.analysis = MagicMock(risk_level=RiskLevel.LOW, summary="Added column")
    return ctx


def test_analyze_appends_focused_erd_to_sub_page():
    """After pipeline, focused ERD must be appended to the analysis sub-page."""
    with patch("lore.cli.load_config", return_value=_make_cfg()), \
         patch("lore.cli.SchemaStore") as mock_store_cls, \
         patch("lore.cli.Pipeline") as mock_pipeline_cls, \
         patch("lore.cli.LarkDocOutput") as mock_lark_cls, \
         patch("lore.cli.generate_mermaid_erd", return_value="erDiagram\n focused") as mock_focused:

        mock_store = MagicMock()
        mock_store.tables = {"user": {"columns": {}}}
        mock_store_cls.return_value = mock_store

        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = _make_pipeline_result()
        mock_pipeline_cls.return_value = mock_pipeline

        mock_lark = MagicMock()
        mock_lark_cls.return_value = mock_lark

        result = runner.invoke(app, ["analyze", "--branch", "feat/test"])
        assert result.exit_code == 0, result.output

        # generate_mermaid_erd called with updated store.tables and correct modified_tables
        mock_focused.assert_called_once_with(mock_store.tables, modified_tables={"user"})
        # Focused ERD appended to sub-page doc ID extracted from output_url
        mock_lark.append_erd_to_doc.assert_called_once_with(
            "sub_doc_789", "erDiagram\n focused"
        )


def test_analyze_skips_erds_when_no_migrations():
    """No ERD updates when no migrations detected."""
    with patch("lore.cli.load_config", return_value=_make_cfg()), \
         patch("lore.cli.SchemaStore") as mock_store_cls, \
         patch("lore.cli.Pipeline") as mock_pipeline_cls, \
         patch("lore.cli.LarkDocOutput") as mock_lark_cls, \
         patch("lore.cli.generate_mermaid_erd") as mock_erd:

        mock_store = MagicMock()
        mock_store_cls.return_value = mock_store

        mock_pipeline = MagicMock()
        no_mig_ctx = MagicMock()
        no_mig_ctx.migrations = []
        mock_pipeline.run.return_value = no_mig_ctx
        mock_pipeline_cls.return_value = mock_pipeline

        mock_lark_cls.return_value = MagicMock()

        result = runner.invoke(app, ["analyze", "--branch", "feat/test"])
        assert result.exit_code == 0
        mock_erd.assert_not_called()
