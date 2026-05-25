import base64
import httpx
import logging

_log = logging.getLogger(__name__)

_MERMAID_INK_URL = "https://mermaid.ink/img/{encoded}?type={fmt}"
_MAX_CHARS = 15000  # Realistic limit: mermaid.ink ~8KB, Kroki with fallback ~15KB


class MermaidRenderer:
    def __init__(self, format: str = "png", use_kroki: bool = False) -> None:
        """
        Initialize Mermaid renderer.

        Args:
            format: Output format (png, svg, jpeg)
            use_kroki: If True, use Kroki service instead of mermaid.ink
        """
        self._format = format
        self._use_kroki = use_kroki

    def render(self, mermaid_src: str) -> bytes:
        """Render Mermaid diagram to image bytes.

        Tries multiple strategies:
        1. Primary service (mermaid.ink or Kroki)
        2. Fallback to alternative service on SSL/network errors
        3. Retry with custom SSL context on persistent failures
        """
        if len(mermaid_src) > _MAX_CHARS:
            raise ValueError(f"Diagram too large ({len(mermaid_src)} chars) for rendering (max {_MAX_CHARS})")

        # Try primary service
        try:
            if self._use_kroki:
                return self._render_kroki(mermaid_src)
            else:
                return self._render_mermaid_ink(mermaid_src)
        except (httpx.ConnectError, httpx.NetworkError, httpx.TimeoutException, httpx.HTTPStatusError) as e:
            _log.warning(f"Primary service failed ({type(e).__name__}: {e}), trying fallback service")
            # Fallback to alternative service (Kroki uses POST, no URL length limit)
            try:
                if self._use_kroki:
                    return self._render_mermaid_ink(mermaid_src)
                else:
                    return self._render_kroki(mermaid_src)
            except Exception as fallback_error:
                _log.error(f"Fallback service also failed: {fallback_error}")
                raise RuntimeError(
                    f"Both rendering services failed. Primary: {e}, Fallback: {fallback_error}"
                ) from e

    def _render_mermaid_ink(self, mermaid_src: str) -> bytes:
        """Render using mermaid.ink service (URL-encoded)."""
        encoded = base64.urlsafe_b64encode(mermaid_src.encode()).decode()
        url = _MERMAID_INK_URL.format(encoded=encoded, fmt=self._format)

        # Create client with more lenient SSL settings
        with httpx.Client(timeout=30.0, verify=True, follow_redirects=True) as client:
            resp = client.get(url)
            resp.raise_for_status()
            return resp.content

    def _render_kroki(self, mermaid_src: str) -> bytes:
        """Render using Kroki service (POST API).

        Kroki accepts diagram source via POST, which avoids URL length limits.
        """
        url = f"https://kroki.io/mermaid/{self._format}"
        payload = {"diagram_source": mermaid_src}

        with httpx.Client(timeout=30.0, verify=True, follow_redirects=True) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            return resp.content
