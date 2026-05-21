import logging
from datetime import date
import httpx
from lore.models import PipelineContext
from lore.outputs.base import OutputPlugin

_log = logging.getLogger(__name__)
_LARK_AUTH_URL = "https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal"
_LARK_DOC_CREATE_URL = "https://open.larksuite.com/open-apis/docx/v1/documents"
_LARK_DOC_UPDATE_URL = "https://open.larksuite.com/open-apis/docx/v1/documents/{document_id}/blocks/{block_id}/children"
_LARK_DOC_RAW_CONTENT_URL = "https://open.larksuite.com/open-apis/docx/v1/documents/{document_id}/raw_content"
_LARK_IMAGE_UPLOAD_URL = "https://open.larksuite.com/open-apis/im/v1/images"


def _get_tenant_token(app_id: str, app_secret: str) -> str:
    resp = httpx.post(_LARK_AUTH_URL, json={"app_id": app_id, "app_secret": app_secret})
    resp.raise_for_status()
    data = resp.json()
    if data.get("code", 0) != 0:
        raise RuntimeError(f"Lark auth failed: {data.get('msg')}")
    return data["tenant_access_token"]


class LarkDocOutput(OutputPlugin):
    def __init__(self, app_id: str, app_secret: str, folder_token: str, parent_doc_id: str = None) -> None:
        """
        Initialize Lark Doc output.

        Args:
            app_id: Lark app ID
            app_secret: Lark app secret
            folder_token: Folder token where docs will be created (from URL)
            parent_doc_id: Optional parent document ID for ERD updates
        """
        self._app_id = app_id
        self._app_secret = app_secret
        self._folder_token = folder_token
        self._parent_doc_id = parent_doc_id

    def _build_title(self, context: PipelineContext, run_date: date) -> str:
        risk = context.analysis.risk_level.value if context.analysis else "UNKNOWN"
        return f"{run_date.isoformat()} | {context.branch} | {risk}"

    def _build_blocks(self, context: PipelineContext, run_date: date) -> list:
        """Build Lark Doc blocks. block_type: 2=text, 3=heading1, 4=heading2, 14=code."""
        report = context.analysis
        if not report:
            return [{"block_type": 2, "text": {"elements": [{"text_run": {"content": "No analysis available."}}]}}]

        def text(content: str, bold: bool = False) -> dict:
            run = {"text_run": {"content": content}}
            if bold:
                run["text_run"]["text_element_style"] = {"bold": True}
            return run

        blocks = [
            {"block_type": 3, "heading1": {"elements": [text("Schema Change Report")]}},
            {"block_type": 2, "text": {"elements": [
                text(f"Branch: {context.branch}\n"),
                text(f"Date: {run_date.isoformat()}\n"),
                text("Risk: ", bold=True),
                text(report.risk_level.value),
            ]}},
            {"block_type": 4, "heading2": {"elements": [text("Summary")]}},
            {"block_type": 2, "text": {"elements": [text(report.summary)]}},
            {"block_type": 4, "heading2": {"elements": [text("Changes")]}},
        ]

        for change in report.changes:
            line = f"• {change.table} — {change.operation.value}"
            if change.column:
                line += f" {change.column}"
            if change.data_type:
                line += f" ({change.data_type})"
            blocks.append({"block_type": 2, "text": {"elements": [text(line)]}})

        blocks.append({"block_type": 4, "heading2": {"elements": [text("Potential Impact")]}})
        for item in report.impact:
            blocks.append({"block_type": 2, "text": {"elements": [text(f"• {item}")]}})

        blocks.extend([
            {"block_type": 4, "heading2": {"elements": [text("Reviewer Notes")]}},
            {"block_type": 2, "text": {"elements": [text(report.reviewer_notes)]}},
        ])

        return blocks

    def run(self, context: PipelineContext) -> PipelineContext:
        run_date = date.today()
        title = self._build_title(context, run_date)

        blocks = self._build_blocks(context, run_date)

        token = _get_tenant_token(self._app_id, self._app_secret)
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        # Create document
        payload = {
            "folder_token": self._folder_token,
            "title": title,
        }
        resp = httpx.post(_LARK_DOC_CREATE_URL, headers=headers, json=payload)
        data = resp.json()

        # Log full response for debugging
        _log.info(f"Lark API Response Status: {resp.status_code}")
        _log.info(f"Lark API Response Body: {data}")

        if resp.status_code != 200:
            error_msg = data.get("msg", "Unknown error")
            raise RuntimeError(f"Lark doc create failed (HTTP {resp.status_code}): {error_msg}\nFull response: {data}")

        if data.get("code", 0) != 0:
            raise RuntimeError(f"Lark doc create failed: {data.get('msg')}\nFull response: {data}")

        doc_data = data.get("data", {}).get("document", {})
        document_id = doc_data.get("document_id")

        if not document_id:
            raise RuntimeError(f"Lark doc create returned unexpected response: {data}")

        url = f"https://open.larksuite.com/docx/{document_id}"

        # In Lark Docs (docx), the root block_id equals the document_id.
        block_url = _LARK_DOC_UPDATE_URL.format(document_id=document_id, block_id=document_id)
        content_payload = {"children": blocks, "index": 0}
        resp = httpx.post(block_url, headers=headers, json=content_payload)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code", 0) != 0:
            raise RuntimeError(f"Lark doc content update failed: {data.get('msg')}")

        context.output_url = url
        return context

    def create_parent_doc(self, title: str = "Lore — Schema ERD") -> tuple[str, str]:
        """Create a new doc in the configured folder, owned by the bot, with a placeholder ERD.

        Returns (document_id, url). Use this to bootstrap a parent doc when the bot
        cannot be added as an editor on a pre-existing doc via Lark's Share dialog.
        """
        token = _get_tenant_token(self._app_id, self._app_secret)
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        resp = httpx.post(_LARK_DOC_CREATE_URL, headers=headers,
                          json={"folder_token": self._folder_token, "title": title})
        data = resp.json()
        if resp.status_code != 200 or data.get("code", 0) != 0:
            raise RuntimeError(f"Lark doc create failed: {data}")

        document_id = data.get("data", {}).get("document", {}).get("document_id")
        if not document_id:
            raise RuntimeError(f"Lark doc create returned unexpected response: {data}")

        seed_blocks = [
            {"block_type": 3, "heading1": {"elements": [{"text_run": {"content": "Schema ERD"}}]}},
            {"block_type": 2, "text": {"elements": [{"text_run": {"content":
                "This doc is auto-updated by Lore on each `lore analyze` run. The Mermaid block below reflects the latest schema snapshot."
            }}]}},
            {"block_type": 14, "code": {
                "elements": [{"text_run": {"content": "erDiagram\n  %% populated by `lore init`"}}],
                "style": {"language": 1},
            }},
        ]
        block_url = _LARK_DOC_UPDATE_URL.format(document_id=document_id, block_id=document_id)
        resp = httpx.post(block_url, headers=headers, json={"children": seed_blocks, "index": 0})
        resp.raise_for_status()
        data = resp.json()
        if data.get("code", 0) != 0:
            raise RuntimeError(f"Lark seed-content insert failed: {data}")

        return document_id, f"https://open.larksuite.com/docx/{document_id}"

    def _upload_image(self, image_bytes: bytes, image_type: str = "image/png") -> str:
        """Upload an image to Lark and return the image_key.

        Args:
            image_bytes: Raw image bytes
            image_type: MIME type (image/png or image/svg+xml)

        Returns:
            image_key that can be used in image blocks
        """
        token = _get_tenant_token(self._app_id, self._app_secret)
        headers = {"Authorization": f"Bearer {token}"}

        files = {
            "image": ("diagram.png", image_bytes, image_type),
            "image_type": (None, "message"),
        }

        resp = httpx.post(_LARK_IMAGE_UPLOAD_URL, headers=headers, files=files, timeout=30.0)
        data = resp.json()

        # Check Lark API error code first (they return 200 even on errors)
        if data.get("code", 0) != 0:
            raise RuntimeError(f"Lark image upload failed: {data.get('msg')} (code: {data.get('code')})")

        resp.raise_for_status()

        image_key = data.get("data", {}).get("image_key")
        if not image_key:
            raise RuntimeError(f"Lark image upload returned no image_key: {data}")

        return image_key

    def update_erd_page(self, mermaid_erd: str, page_token: str = None, render_as_image: bool = True) -> None:
        """Update the ERD in the parent Lark Doc.

        Args:
            mermaid_erd: Mermaid diagram source code
            page_token: Optional Lark Doc ID (uses parent_doc_id if not provided)
            render_as_image: If True, render to PNG and upload as image block. If False, upload as code block.
        """
        if not self._parent_doc_id and not page_token:
            _log.warning("No parent document ID provided, skipping ERD update")
            return

        doc_id = page_token or self._parent_doc_id
        token = _get_tenant_token(self._app_id, self._app_secret)
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        # Large ERDs (>5KB) typically fail URL length limits, fall back to code block
        if render_as_image and len(mermaid_erd) <= 5000:
            # Render Mermaid to image and upload as image block
            from lore.mermaid_renderer import MermaidRenderer
            renderer = MermaidRenderer(format="png")
            try:
                image_bytes = renderer.render(mermaid_erd)
                # mermaid.ink returns JPEG despite "png" in URL
                image_key = self._upload_image(image_bytes, image_type="image/jpeg")

                # block_type: 3=heading1, 27=image
                erd_blocks = [
                    {"block_type": 3, "heading1": {"elements": [{"text_run": {"content": "Entity Relationship Diagram"}}]}},
                    {"block_type": 27, "image": {"token": image_key}},
                ]
            except Exception as e:
                _log.warning(f"Failed to render ERD as image: {e}. Falling back to code block.")
                render_as_image = False
        elif render_as_image:
            _log.info(f"ERD too large ({len(mermaid_erd)} chars) for image rendering, using code block")
            render_as_image = False

        if not render_as_image:
            # Fallback: Mermaid posted as a plain code block. block_type: 14=code.
            erd_blocks = [
                {"block_type": 3, "heading1": {"elements": [{"text_run": {"content": "Entity Relationship Diagram"}}]}},
                {"block_type": 14, "code": {
                    "elements": [{"text_run": {"content": mermaid_erd}}],
                    "style": {"language": 1},
                }},
            ]

        # In Lark Docs (docx), the root block_id equals the document_id.
        block_url = _LARK_DOC_UPDATE_URL.format(document_id=doc_id, block_id=doc_id)
        payload = {"children": erd_blocks, "index": -1}
        resp = httpx.post(block_url, headers=headers, json=payload)
        if resp.status_code == 403:
            raise RuntimeError(
                f"Lark doc ERD update failed with 403 Forbidden on parent doc {doc_id}. "
                "The bot needs editor access. Easiest fix: run `lore init-parent` to create "
                "a fresh parent doc the bot owns, then update LARK_PARENT_DOC_ID to its id."
            )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code", 0) != 0:
            raise RuntimeError(f"Lark doc ERD update failed: {data.get('msg')}")

    def append_erd_to_doc(self, document_id: str | None, mermaid_erd: str) -> None:
        """Append a focused ERD section to an existing Lark Doc (e.g. an analysis sub-page).

        Args:
            document_id: Lark Doc ID to append to. No-op if None.
            mermaid_erd: Mermaid diagram source to append as a code block.
        """
        if not document_id:
            _log.warning("No document_id provided to append_erd_to_doc, skipping")
            return

        token = _get_tenant_token(self._app_id, self._app_secret)
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        erd_blocks = [
            {"block_type": 3, "heading1": {"elements": [{"text_run": {"content": "Affected Tables — ERD"}}]}},
            {"block_type": 14, "code": {
                "elements": [{"text_run": {"content": mermaid_erd}}],
                "style": {"language": 1},
            }},
        ]

        block_url = _LARK_DOC_UPDATE_URL.format(document_id=document_id, block_id=document_id)
        resp = httpx.post(block_url, headers=headers, json={"children": erd_blocks, "index": -1})
        data = resp.json()
        if data.get("code", 0) != 0:
            raise RuntimeError(f"Lark doc ERD append failed: {data.get('msg')}")
        resp.raise_for_status()

    def upload_category_erds(self, erd_map: dict[str, str], page_token: str = None, max_categories: int = 20, render_as_image: bool = True) -> None:
        """Upload multiple category ERDs to a Lark Doc.

        Args:
            erd_map: Dict mapping category name to Mermaid ERD content
            page_token: Optional Lark Doc ID (uses parent_doc_id if not provided)
            max_categories: Maximum number of categories to upload (to avoid hitting size limits)
            render_as_image: If True, render to PNG and upload as image blocks. If False, upload as code blocks.
        """
        if not self._parent_doc_id and not page_token:
            _log.warning("No parent document ID provided, skipping ERD upload")
            return

        doc_id = page_token or self._parent_doc_id
        token = _get_tenant_token(self._app_id, self._app_secret)
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        # Build blocks for all categories
        all_blocks = [
            {"block_type": 3, "heading1": {"elements": [{"text_run": {"content": "Schema ERDs by Category"}}]}},
        ]

        # Sort by table count (largest first) and limit to max_categories
        sorted_categories = sorted(erd_map.items(), key=lambda x: x[1].count(" {"), reverse=True)[:max_categories]

        if render_as_image:
            from lore.mermaid_renderer import MermaidRenderer
            renderer = MermaidRenderer(format="png")

        for category, erd_content in sorted_categories:
            table_count = erd_content.count(" {")
            all_blocks.append({"block_type": 4, "heading2": {"elements": [{"text_run": {"content": f"{category} ({table_count} tables)"}}]}})

            # Try image rendering for smaller ERDs (URL length limit ~5KB)
            if render_as_image and len(erd_content) <= 5000:
                try:
                    image_bytes = renderer.render(erd_content)
                    # mermaid.ink returns JPEG despite "png" in URL
                    image_key = self._upload_image(image_bytes, image_type="image/jpeg")
                    all_blocks.append({"block_type": 27, "image": {"token": image_key}})
                    _log.info(f"Rendered {category} ERD as image ({len(erd_content)} chars)")
                except Exception as e:
                    _log.warning(f"Failed to render {category} ERD as image: {e}. Using code block.")
                    all_blocks.append({"block_type": 14, "code": {
                        "elements": [{"text_run": {"content": erd_content}}],
                        "style": {"language": 1},
                    }})
            else:
                if render_as_image:
                    _log.info(f"Skipping {category} (ERD too large: {len(erd_content)} chars)")
                    # Skip code block to avoid hitting 100K char limit
                    continue
                all_blocks.append({"block_type": 14, "code": {
                    "elements": [{"text_run": {"content": erd_content}}],
                    "style": {"language": 1},
                }})

        if len(erd_map) > max_categories:
            remaining = len(erd_map) - max_categories
            all_blocks.append({"block_type": 2, "text": {"elements": [{"text_run": {
                "content": f"... and {remaining} more categories (showing top {max_categories} by table count)"
            }}]}})

        # Upload to Lark Doc
        block_url = _LARK_DOC_UPDATE_URL.format(document_id=doc_id, block_id=doc_id)
        payload = {"children": all_blocks, "index": -1}
        resp = httpx.post(block_url, headers=headers, json=payload)
        if resp.status_code == 403:
            raise RuntimeError(
                f"Lark doc upload failed with 403 Forbidden on doc {doc_id}. "
                "The bot needs editor access."
            )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code", 0) != 0:
            raise RuntimeError(f"Lark doc upload failed: {data.get('msg')}")
