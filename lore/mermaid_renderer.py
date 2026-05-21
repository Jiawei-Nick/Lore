import base64
import httpx

_MERMAID_INK_URL = "https://mermaid.ink/img/{encoded}?type={fmt}"
_MAX_CHARS = 5000


class MermaidRenderer:
    def __init__(self, format: str = "png") -> None:
        self._format = format

    def render(self, mermaid_src: str) -> bytes:
        if len(mermaid_src) > _MAX_CHARS:
            raise ValueError(f"Diagram too large ({len(mermaid_src)} chars) for mermaid.ink (max {_MAX_CHARS})")
        encoded = base64.urlsafe_b64encode(mermaid_src.encode()).decode()
        url = _MERMAID_INK_URL.format(encoded=encoded, fmt=self._format)
        resp = httpx.get(url, timeout=30.0, follow_redirects=True)
        resp.raise_for_status()
        return resp.content
