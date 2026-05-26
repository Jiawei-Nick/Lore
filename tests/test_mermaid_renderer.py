import base64
from unittest.mock import MagicMock, patch
import pytest
from lore.mermaid_renderer import MermaidRenderer, _MAX_CHARS, _MERMAID_INK_URL


def _make_renderer(fmt: str = "png") -> MermaidRenderer:
    return MermaidRenderer(format=fmt)


def _mock_client_get(content: bytes = b"\xff\xd8\xff"):
    """Return a context-manager-compatible mock for httpx.Client."""
    mock_resp = MagicMock()
    mock_resp.content = content
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.get.return_value = mock_resp
    return mock_client, mock_resp


@patch("lore.mermaid_renderer.httpx.Client")
def test_render_returns_bytes(mock_client_cls):
    mock_client, mock_resp = _mock_client_get(b"\xff\xd8\xff")
    mock_client_cls.return_value = mock_client

    result = _make_renderer().render("graph TD; A-->B")

    assert result == b"\xff\xd8\xff"
    mock_resp.raise_for_status.assert_called_once()


@patch("lore.mermaid_renderer.httpx.Client")
def test_render_builds_correct_url(mock_client_cls):
    mock_client, _ = _mock_client_get(b"img")
    mock_client_cls.return_value = mock_client

    src = "graph TD; A-->B"
    _make_renderer(fmt="jpeg").render(src)

    expected_encoded = base64.urlsafe_b64encode(src.encode()).decode()
    expected_url = _MERMAID_INK_URL.format(encoded=expected_encoded, fmt="jpeg")
    mock_client.get.assert_called_once_with(expected_url)


def test_render_raises_on_oversized_diagram():
    oversized = "A" * (_MAX_CHARS + 1)
    with pytest.raises(ValueError, match="too large"):
        _make_renderer().render(oversized)


@patch("lore.mermaid_renderer.httpx.Client")
def test_render_exactly_at_size_limit_does_not_raise(mock_client_cls):
    mock_client, _ = _mock_client_get(b"img")
    mock_client_cls.return_value = mock_client

    at_limit = "A" * _MAX_CHARS
    _make_renderer().render(at_limit)  # should not raise


@patch("lore.mermaid_renderer.httpx.Client")
def test_render_propagates_http_error(mock_client_cls):
    import httpx as _httpx

    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = _httpx.HTTPStatusError(
        "404", request=MagicMock(), response=MagicMock()
    )
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.get.return_value = mock_resp
    # Kroki POST also needs to fail for the error to propagate
    mock_client.post.return_value = mock_resp
    mock_client_cls.return_value = mock_client

    with pytest.raises(RuntimeError):
        _make_renderer().render("graph TD; A-->B")
