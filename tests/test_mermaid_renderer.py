import base64
from unittest.mock import MagicMock, patch
import pytest
from lore.mermaid_renderer import MermaidRenderer, _MAX_CHARS, _MERMAID_INK_URL


def _make_renderer(fmt: str = "png") -> MermaidRenderer:
    return MermaidRenderer(format=fmt)


@patch("httpx.get")
def test_render_returns_bytes(mock_get):
    mock_resp = MagicMock()
    mock_resp.content = b"\xff\xd8\xff"  # JPEG magic bytes
    mock_get.return_value = mock_resp

    result = _make_renderer().render("graph TD; A-->B")

    assert result == b"\xff\xd8\xff"
    mock_resp.raise_for_status.assert_called_once()


@patch("httpx.get")
def test_render_builds_correct_url(mock_get):
    mock_resp = MagicMock()
    mock_resp.content = b"img"
    mock_get.return_value = mock_resp

    src = "graph TD; A-->B"
    _make_renderer(fmt="jpeg").render(src)

    expected_encoded = base64.urlsafe_b64encode(src.encode()).decode()
    expected_url = _MERMAID_INK_URL.format(encoded=expected_encoded, fmt="jpeg")
    mock_get.assert_called_once_with(expected_url, timeout=30.0, follow_redirects=True)


def test_render_raises_on_oversized_diagram():
    oversized = "A" * (_MAX_CHARS + 1)
    with pytest.raises(ValueError, match="too large"):
        _make_renderer().render(oversized)


def test_render_exactly_at_size_limit_does_not_raise():
    at_limit = "A" * _MAX_CHARS
    with patch("httpx.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.content = b"img"
        mock_get.return_value = mock_resp
        _make_renderer().render(at_limit)  # should not raise


@patch("httpx.get")
def test_render_propagates_http_error(mock_get):
    import httpx as _httpx
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = _httpx.HTTPStatusError(
        "404", request=MagicMock(), response=MagicMock()
    )
    mock_get.return_value = mock_resp

    with pytest.raises(_httpx.HTTPStatusError):
        _make_renderer().render("graph TD; A-->B")
