from unittest.mock import patch, MagicMock
from lore.outputs.lark_doc import LarkDocOutput


def _make_output():
    return LarkDocOutput(
        app_id="test_app",
        app_secret="test_secret",
        folder_token="test_folder",
        parent_doc_id="parent_doc_123",
    )


def test_append_erd_to_doc_posts_heading_and_code_block():
    output = _make_output()

    with patch("lore.outputs.lark_doc._get_tenant_token", return_value="tok"), \
         patch("httpx.post") as mock_post:
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"code": 0}
        )
        output.append_erd_to_doc("sub_doc_456", "erDiagram\n  user { BIGINT id }")

    mock_post.assert_called_once()
    payload = mock_post.call_args[1]["json"]
    block_types = [b["block_type"] for b in payload["children"]]
    assert 3 in block_types   # heading1
    assert 14 in block_types  # code block
    assert payload["index"] == -1

    all_text = str(payload)
    assert "erDiagram" in all_text
    assert "Affected Tables" in all_text


def test_append_erd_to_doc_raises_on_lark_error():
    output = _make_output()

    with patch("lore.outputs.lark_doc._get_tenant_token", return_value="tok"), \
         patch("httpx.post") as mock_post:
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"code": 99, "msg": "permission denied"}
        )
        try:
            output.append_erd_to_doc("sub_doc_456", "erDiagram")
            assert False, "Expected RuntimeError"
        except RuntimeError as e:
            assert "permission denied" in str(e)


def test_append_erd_to_doc_skips_if_no_doc_id():
    output = _make_output()
    with patch("lore.outputs.lark_doc._get_tenant_token") as mock_token:
        output.append_erd_to_doc(None, "erDiagram")
        mock_token.assert_not_called()


def test_build_blocks_no_erd_section():
    """_build_blocks no longer embeds ERD — verify ERD content absent."""
    from datetime import date
    from unittest.mock import MagicMock
    from lore.models import RiskLevel
    output = _make_output()
    ctx = MagicMock()
    ctx.branch = "feat/test"
    report = MagicMock()
    report.risk_level = RiskLevel.LOW
    report.summary = "Added column"
    report.changes = []
    report.impact = []
    report.reviewer_notes = "None"
    ctx.analysis = report
    blocks = output._build_blocks(ctx, date.today())
    all_text = str(blocks)
    assert "Affected Tables" not in all_text
    assert "erDiagram" not in all_text
