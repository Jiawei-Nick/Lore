import logging
import base64
import httpx
from pathlib import Path

_log = logging.getLogger(__name__)


class MermaidRenderer:
    """Renders Mermaid diagrams to images using mermaid.ink API."""

    def __init__(self, format: str = "png"):
        """
        Initialize renderer.

        Args:
            format: Output format ('png' or 'svg')
        """
        if format not in ("png", "svg"):
            raise ValueError(f"Unsupported format: {format}")
        self.format = format
        self._base_url = f"https://mermaid.ink/img"

    def render(self, mermaid_code: str) -> bytes:
        """
        Render Mermaid code to image bytes.

        Args:
            mermaid_code: Mermaid diagram source code

        Returns:
            Image bytes (PNG or SVG)

        Raises:
            RuntimeError: If rendering fails
        """
        # mermaid.ink expects base64-encoded Mermaid source
        encoded = base64.urlsafe_b64encode(mermaid_code.encode("utf-8")).decode("ascii")
        url = f"{self._base_url}/{encoded}"

        try:
            # Create client with custom SSL context to handle mermaid.ink
            import ssl
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

            with httpx.Client(verify=False, timeout=30.0) as client:
                resp = client.get(url)
                resp.raise_for_status()
                return resp.content
        except httpx.HTTPError as e:
            raise RuntimeError(f"Mermaid rendering failed: {e}")

    def render_to_file(self, mermaid_code: str, output_path: Path) -> None:
        """
        Render Mermaid code and save to file.

        Args:
            mermaid_code: Mermaid diagram source code
            output_path: Path to save the rendered image
        """
        image_bytes = self.render(mermaid_code)
        output_path.write_bytes(image_bytes)
        _log.info(f"Saved rendered diagram to {output_path}")