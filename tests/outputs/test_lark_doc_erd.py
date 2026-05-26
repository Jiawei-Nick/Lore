from unittest.mock import patch, MagicMock, call
from lore.outputs.lark_doc import LarkDocOutput


def _make_output():
    return LarkDocOutput(
        app_id="test_app",
        app_secret="test_secret",
        folder_token="test_folder",
        parent_doc_id="parent_doc_123",
    )


def _post_side_effect(url, **kwargs):
    """Return appropriate responses for each POST in the 3-step image flow."""
    resp = MagicMock(status_code=200)
    children = (kwargs.get("json") or {}).get("children", [])
    if children and children[0].get("block_type") == 27:
        resp.json.return_value = {"code": 0, "data": {"children": ["img_block_id_123"]}}
    else:
        resp.json.return_value = {"code": 0}
    return resp


def test_append_erd_to_doc_posts_heading_and_code_block():
    output = _make_output()

    mock_renderer = MagicMock()
    mock_renderer.render.return_value = b"\xff\xd8\xff"

    with patch("lore.outputs.lark_doc._get_tenant_token", return_value="tok"), \
         patch("lore.outputs.lark_doc.httpx.post", side_effect=_post_side_effect) as mock_post, \
         patch("lore.outputs.lark_doc.httpx.patch") as mock_patch, \
         patch("lore.outputs.lark_doc.MermaidRenderer", return_value=mock_renderer), \
         patch.object(output, "_upload_image", return_value="file_tok_123"):
        mock_patch.return_value = MagicMock(status_code=200, json=lambda: {"code": 0})
        output.append_erd_to_doc("sub_doc_456", "erDiagram\n  user { BIGINT id }")

    # First POST: heading + code. Second POST: empty image block.
    assert mock_post.call_count == 2
    first_payload = mock_post.call_args_list[0][1]["json"]
    block_types = [b["block_type"] for b in first_payload["children"]]
    assert 3 in block_types
    assert 14 in block_types
    assert first_payload["index"] == -1
    all_text = str(first_payload)
    assert "erDiagram" in all_text
    assert "Affected Tables" in all_text

    # PATCH replaces image token
    mock_patch.assert_called_once()
    assert mock_patch.call_args[1]["json"]["replace_image"]["token"] == "file_tok_123"


def test_append_erd_to_doc_skips_image_on_render_failure():
    output = _make_output()

    mock_renderer = MagicMock()
    mock_renderer.render.side_effect = RuntimeError("render failed")

    with patch("lore.outputs.lark_doc._get_tenant_token", return_value="tok"), \
         patch("lore.outputs.lark_doc.httpx.post") as mock_post, \
         patch("lore.outputs.lark_doc.MermaidRenderer", return_value=mock_renderer):
        mock_post.return_value = MagicMock(status_code=200, json=lambda: {"code": 0})
        output.append_erd_to_doc("sub_doc_456", "erDiagram\n  A ||--o{ B : has")

    # Only the heading+code POST, no image block POST
    assert mock_post.call_count == 1


def test_append_erd_to_doc_skips_image_for_large_erd():
    output = _make_output()
    large_erd = "A" * 5001

    with patch("lore.outputs.lark_doc._get_tenant_token", return_value="tok"), \
         patch("lore.outputs.lark_doc.httpx.post") as mock_post, \
         patch("lore.outputs.lark_doc.MermaidRenderer") as mock_renderer_cls:
        mock_post.return_value = MagicMock(status_code=200, json=lambda: {"code": 0})
        output.append_erd_to_doc("sub_doc_456", large_erd)

    mock_renderer_cls.assert_not_called()
    assert mock_post.call_count == 1


def test_append_erd_to_doc_raises_on_lark_error():
    output = _make_output()

    with patch("lore.outputs.lark_doc._get_tenant_token", return_value="tok"), \
         patch("lore.outputs.lark_doc.httpx.post") as mock_post:
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
    from datetime import datetime, timezone
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
    blocks = output._build_blocks(ctx, datetime.now(tz=timezone.utc))
    all_text = str(blocks)
    assert "Affected Tables" not in all_text
    assert "erDiagram" not in all_text
