import logging
from datetime import date, datetime, timezone
import time
import httpx
from lore.models import PipelineContext
from lore.outputs.base import OutputPlugin
from lore.mermaid_renderer import MermaidRenderer

_log = logging.getLogger(__name__)
_LARK_AUTH_URL = "https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal"
_LARK_DOC_CREATE_URL = "https://open.larksuite.com/open-apis/docx/v1/documents"
_LARK_DOC_UPDATE_URL = "https://open.larksuite.com/open-apis/docx/v1/documents/{document_id}/blocks/{block_id}/children"
_LARK_DOC_RAW_CONTENT_URL = "https://open.larksuite.com/open-apis/docx/v1/documents/{document_id}/raw_content"
_LARK_IMAGE_UPLOAD_URL = "https://open.larksuite.com/open-apis/drive/v1/medias/upload_all"  # Drive API for doc images
_LARK_FOLDER_CREATE_URL = "https://open.larksuite.com/open-apis/drive/v1/files/create_folder"  # Drive API for folder creation
_LARK_FILE_MOVE_URL = "https://open.larksuite.com/open-apis/drive/v1/files/{file_token}/move"  # Drive API for moving files


def _safe_http_request(method: str, url: str, max_retries: int = 2, **kwargs) -> httpx.Response:
    """Make an HTTP request with retry logic and better error messages.

    Args:
        method: HTTP method (GET, POST, PATCH, DELETE)
        url: Request URL
        max_retries: Maximum retry attempts for transient failures
        **kwargs: Additional arguments passed to httpx request

    Returns:
        httpx.Response object

    Raises:
        RuntimeError: On persistent network/HTTP errors
    """
    last_error = None

    # Set default timeout if not provided
    if "timeout" not in kwargs:
        kwargs["timeout"] = 30.0

    for attempt in range(max_retries):
        try:
            if method.upper() == "GET":
                resp = httpx.get(url, **kwargs)
            elif method.upper() == "POST":
                resp = httpx.post(url, **kwargs)
            elif method.upper() == "PATCH":
                resp = httpx.patch(url, **kwargs)
            elif method.upper() == "DELETE":
                resp = httpx.delete(url, **kwargs)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            return resp

        except httpx.ConnectError as e:
            last_error = e
            error_msg = str(e)

            if "SSL" in error_msg or "TLS" in error_msg or "handshake" in error_msg:
                _log.warning(
                    f"SSL/TLS connection failed (attempt {attempt + 1}/{max_retries}) to {url}: {error_msg}"
                )
            else:
                _log.warning(
                    f"Connection failed (attempt {attempt + 1}/{max_retries}) to {url}: {error_msg}"
                )

            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                time.sleep(wait_time)

        except httpx.TimeoutException as e:
            last_error = e
            _log.warning(f"Request timeout (attempt {attempt + 1}/{max_retries}) to {url}: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)

    # All retries exhausted
    raise RuntimeError(
        f"HTTP {method} request to {url} failed after {max_retries} attempts. "
        f"Last error: {last_error}"
    )


def _get_tenant_token(app_id: str, app_secret: str, max_retries: int = 3) -> str:
    """Get Lark tenant access token with retry logic for network failures.

    Args:
        app_id: Lark app ID
        app_secret: Lark app secret
        max_retries: Maximum number of retry attempts (default: 3)

    Returns:
        Tenant access token string

    Raises:
        RuntimeError: If auth fails after all retries
    """
    last_error = None

    for attempt in range(max_retries):
        try:
            resp = httpx.post(
                _LARK_AUTH_URL,
                json={"app_id": app_id, "app_secret": app_secret},
                timeout=30.0
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("code", 0) != 0:
                raise RuntimeError(f"Lark auth failed: {data.get('msg')}")
            return data["tenant_access_token"]

        except httpx.ConnectError as e:
            last_error = e
            error_msg = str(e)

            # Provide specific guidance for SSL errors
            if "SSL" in error_msg or "TLS" in error_msg or "handshake" in error_msg:
                _log.warning(
                    f"SSL/TLS handshake failure (attempt {attempt + 1}/{max_retries}). "
                    f"This may be caused by: corporate proxy, firewall, or expired certificates. "
                    f"Error: {error_msg}"
                )
            else:
                _log.warning(
                    f"Network connection failed (attempt {attempt + 1}/{max_retries}): {error_msg}"
                )

            # Retry with exponential backoff
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # 1s, 2s, 4s
                _log.info(f"Retrying in {wait_time}s...")
                time.sleep(wait_time)

        except httpx.TimeoutException as e:
            last_error = e
            _log.warning(f"Request timeout (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)

        except httpx.HTTPStatusError as e:
            # Don't retry on HTTP errors (likely auth/permission issues)
            raise RuntimeError(f"Lark auth HTTP error: {e}")

    # All retries exhausted
    raise RuntimeError(
        f"Lark authentication failed after {max_retries} attempts. "
        f"Last error: {last_error}. "
        f"Please check: (1) network connectivity, (2) firewall/proxy settings, "
        f"(3) SSL certificate validity, (4) Lark API credentials."
    )


class LarkDocOutput(OutputPlugin):
    def __init__(self, app_id: str, app_secret: str, folder_token: str, parent_doc_id: str = None, base_url: str = "open.larksuite.com") -> None:
        self._app_id = app_id
        self._app_secret = app_secret
        self._folder_token = folder_token
        self._parent_doc_id = parent_doc_id
        self._base_url = base_url.rstrip("/")

    def _build_title(self, context: PipelineContext, run_dt: datetime) -> str:
        risk = context.analysis.risk_level.value if context.analysis else "UNKNOWN"
        return f"{run_dt.strftime('%Y-%m-%d %H:%M %z')} | {context.branch} | {risk}"

    def _build_blocks(self, context: PipelineContext, run_dt: datetime) -> list:
        """Build Lark Doc blocks. block_type: 2=text, 3=heading1, 4=heading2, 14=code."""
        report = context.analysis
        if not report:
            return [{"block_type": 2, "text": {"elements": [{"text_run": {"content": "No analysis available."}}]}}]

        def text(content: str, bold: bool = False, color: int = None) -> dict:
            run = {"text_run": {"content": content}}
            style = {}
            if bold:
                style["bold"] = True
            if color:
                style["text_color"] = color
            if style:
                run["text_run"]["text_element_style"] = style
            return run

        # Map risk levels to colors (Lark text color codes: 1-7)
        # Based on Lark API docs: 1=red, 2=orange, 3=yellow, 4=green, 5=blue, 6=purple, 7=gray
        risk_colors = {
            "LOW": 4,     # green
            "MEDIUM": 3,  # yellow
            "HIGH": 1     # red
        }
        risk_color = risk_colors.get(report.risk_level.value, None)

        blocks = [
            {"block_type": 3, "heading1": {"elements": [text("Schema Change Report")]}},
            {"block_type": 2, "text": {"elements": [
                text(f"Branch: {context.branch}\n"),
                text(f"Date: {run_dt.strftime('%Y-%m-%d %H:%M %z')}\n"),
                text("Risk: ", bold=True),
                text(report.risk_level.value, bold=True, color=risk_color),
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
        """Upload analysis report to Lark Docs.

        Raises:
            RuntimeError: On network/auth/API errors with detailed troubleshooting info
        """
        run_dt = datetime.now(tz=timezone.utc)
        title = self._build_title(context, run_dt)
        blocks = self._build_blocks(context, run_dt)

        try:
            token = _get_tenant_token(self._app_id, self._app_secret)
        except RuntimeError as e:
            _log.error(f"Failed to authenticate with Lark: {e}")
            raise RuntimeError(
                f"Lark authentication failed. Please verify:\n"
                f"  1. LARK_APP_ID and LARK_APP_SECRET are correct\n"
                f"  2. Network/firewall allows connections to open.larksuite.com\n"
                f"  3. SSL certificates are valid\n"
                f"Original error: {e}"
            )

        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        # Create document
        payload = {
            "folder_token": self._folder_token,
            "title": title,
        }

        try:
            resp = _safe_http_request("POST", _LARK_DOC_CREATE_URL, headers=headers, json=payload)
            data = resp.json()

            # Log full response for debugging
            _log.info(f"Lark API Response Status: {resp.status_code}")
            _log.debug(f"Lark API Response Body: {data}")

            if resp.status_code != 200:
                error_msg = data.get("msg", "Unknown error")
                raise RuntimeError(f"Lark doc create failed (HTTP {resp.status_code}): {error_msg}\nFull response: {data}")

            if data.get("code", 0) != 0:
                raise RuntimeError(f"Lark doc create failed: {data.get('msg')}\nFull response: {data}")

            doc_data = data.get("data", {}).get("document", {})
            document_id = doc_data.get("document_id")

            if not document_id:
                raise RuntimeError(f"Lark doc create returned unexpected response: {data}")

            url = f"https://{self._base_url}/docx/{document_id}"

        except RuntimeError as e:
            if "SSL" in str(e) or "TLS" in str(e):
                raise RuntimeError(
                    f"Network/SSL error when creating Lark document.\n"
                    f"Possible causes:\n"
                    f"  - Corporate proxy intercepting SSL connections\n"
                    f"  - Firewall blocking HTTPS to open.larksuite.com\n"
                    f"  - Expired/invalid SSL certificates\n"
                    f"Original error: {e}"
                )
            raise

        # In Lark Docs (docx), the root block_id equals the document_id.
        block_url = _LARK_DOC_UPDATE_URL.format(document_id=document_id, block_id=document_id)
        content_payload = {"children": blocks, "index": 0}

        try:
            resp = _safe_http_request("POST", block_url, headers=headers, json=content_payload)

            # Log response for debugging
            if resp.status_code != 200:
                _log.error(f"Lark API error: {resp.status_code}")
                _log.error(f"Response body: {resp.text}")

            resp.raise_for_status()
            data = resp.json()
            if data.get("code", 0) != 0:
                raise RuntimeError(f"Lark doc content update failed: {data.get('msg')}")

        except RuntimeError as e:
            _log.error(f"Failed to update document content: {e}")
            _log.info(f"Document was created but content upload failed. URL: {url}")
            # Still return the URL so user can access the partial document
            context.output_url = url
            raise

        context.output_url = url
        _log.info(f"Successfully uploaded analysis to Lark: {url}")
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

        return document_id, f"https://{self._base_url}/docx/{document_id}"

    def create_folder(self, name: str, parent_folder_token: str) -> str:
        """Create a folder in Lark Drive.

        Args:
            name: Folder name
            parent_folder_token: Parent folder token

        Returns:
            folder_token of the created folder
        """
        token = _get_tenant_token(self._app_id, self._app_secret)
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        payload = {
            "name": name,
            "folder_token": parent_folder_token,
        }

        try:
            resp = _safe_http_request("POST", _LARK_FOLDER_CREATE_URL, headers=headers, json=payload, timeout=30.0)
            data = resp.json()

            if data.get("code", 0) != 0:
                raise RuntimeError(f"Lark folder creation failed: {data.get('msg')} (code: {data.get('code')})")

            resp.raise_for_status()

            folder_token = data.get("data", {}).get("token")
            if not folder_token:
                raise RuntimeError(f"Lark folder creation returned no token: {data}")

            _log.info(f"Created folder '{name}' with token {folder_token}")
            return folder_token

        except RuntimeError as e:
            _log.error(f"Failed to create folder '{name}': {e}")
            raise

    def move_document_to_folder(self, document_id: str, target_folder_token: str) -> None:
        """Move a document to a specific folder.

        Args:
            document_id: Document ID to move
            target_folder_token: Target folder token
        """
        token = _get_tenant_token(self._app_id, self._app_secret)
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        # Convert document_id to file_token format
        file_token = document_id

        payload = {
            "type": "docx",
            "folder_token": target_folder_token,
        }

        move_url = _LARK_FILE_MOVE_URL.format(file_token=file_token)
        resp = httpx.post(move_url, headers=headers, json=payload, timeout=30.0)
        data = resp.json()

        if data.get("code", 0) != 0:
            raise RuntimeError(f"Lark file move failed: {data.get('msg')} (code: {data.get('code')})")

        resp.raise_for_status()

    def _replace_erd_blocks(self, doc_id: str, new_erd_blocks: list, headers: dict) -> None:
        """Replace existing ERD blocks with new ones, preserving other content.

        Finds blocks with heading "Entity Relationship Diagram" and replaces them.
        """
        # List all blocks
        list_url = f"https://open.larksuite.com/open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}/children"
        params = {"page_size": 500}

        all_blocks = []
        page_token = None

        while True:
            if page_token:
                params["page_token"] = page_token

            resp = httpx.get(list_url, headers=headers, params=params)
            data = resp.json()

            if data.get("code", 0) != 0:
                _log.warning(f"Failed to list blocks: {data.get('msg')}")
                # Fall back to append mode
                block_url = _LARK_DOC_UPDATE_URL.format(document_id=doc_id, block_id=doc_id)
                payload = {"children": new_erd_blocks, "index": -1}
                httpx.post(block_url, headers=headers, json=payload)
                return

            items = data.get("data", {}).get("items", [])
            all_blocks.extend(items)

            if not data.get("data", {}).get("has_more"):
                break
            page_token = data.get("data", {}).get("page_token")

        # Find ERD section (heading1 with text "Entity Relationship Diagram")
        erd_start_idx = None
        erd_block_ids = []

        for idx, block in enumerate(all_blocks):
            block_type = block.get("block_type")
            # Check for heading1 with "Entity Relationship Diagram"
            if block_type == 3:  # heading1
                heading_data = block.get("heading1", {})
                elements = heading_data.get("elements", [])
                if elements and any("Entity Relationship Diagram" in elem.get("text_run", {}).get("content", "") for elem in elements):
                    erd_start_idx = idx
                    erd_block_ids.append(block["block_id"])
                    # Collect the next block (image or code block)
                    if idx + 1 < len(all_blocks):
                        erd_block_ids.append(all_blocks[idx + 1]["block_id"])
                    break

        # Delete old ERD blocks
        if erd_block_ids:
            for block_id in erd_block_ids:
                delete_url = f"https://open.larksuite.com/open-apis/docx/v1/documents/{doc_id}/blocks/{block_id}"
                try:
                    httpx.delete(delete_url, headers=headers)
                except Exception as e:
                    _log.debug(f"Failed to delete block {block_id}: {e}")

        # Insert new ERD blocks at the same position or at end
        block_url = _LARK_DOC_UPDATE_URL.format(document_id=doc_id, block_id=doc_id)
        insert_index = erd_start_idx if erd_start_idx is not None else -1
        payload = {"children": new_erd_blocks, "index": insert_index}

        resp = httpx.post(block_url, headers=headers, json=payload)
        if resp.status_code == 403:
            raise RuntimeError(
                f"Lark doc ERD update failed with 403 Forbidden on doc {doc_id}. "
                "The bot needs editor access."
            )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code", 0) != 0:
            raise RuntimeError(f"Lark doc ERD update failed: {data.get('msg')}")

        _log.info(f"Replaced ERD blocks in document {doc_id}")

    def _clear_document(self, doc_id: str) -> None:
        """Delete all blocks in a document to start fresh."""
        token = _get_tenant_token(self._app_id, self._app_secret)
        headers = {"Authorization": f"Bearer {token}"}

        # List all blocks
        list_url = f"https://open.larksuite.com/open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}/children"
        params = {"page_size": 500}

        all_block_ids = []
        page_token = None

        while True:
            if page_token:
                params["page_token"] = page_token

            resp = httpx.get(list_url, headers=headers, params=params)
            data = resp.json()

            if data.get("code", 0) != 0:
                _log.warning(f"Failed to list blocks: {data.get('msg')}")
                break

            items = data.get("data", {}).get("items", [])
            all_block_ids.extend([item["block_id"] for item in items])

            if not data.get("data", {}).get("has_more"):
                break
            page_token = data.get("data", {}).get("page_token")

        # Delete blocks individually (Lark batch delete endpoint seems unavailable)
        if all_block_ids:
            deleted_count = 0
            for block_id in all_block_ids:
                delete_url = f"https://open.larksuite.com/open-apis/docx/v1/documents/{doc_id}/blocks/{block_id}"
                try:
                    resp = httpx.delete(delete_url, headers=headers)
                    if resp.status_code in (200, 204):
                        deleted_count += 1
                except Exception as e:
                    _log.debug(f"Failed to delete block {block_id}: {e}")

            _log.info(f"Cleared {deleted_count}/{len(all_block_ids)} blocks from document")

    def _upload_image(self, image_bytes: bytes, image_type: str = "image/png", filename: str = "diagram.png", save_locally: bool = False, local_dir: str = None, parent_type: str = "explorer", parent_node: str = None) -> str:
        """Upload an image to Lark Drive and return the file_token.

        Args:
            image_bytes: Raw image bytes
            image_type: MIME type (image/png or image/jpeg)
            filename: Name for the uploaded file (default: diagram.png)
            save_locally: If True, save image to local disk in addition to uploading
            local_dir: Local directory to save images (default: "ERD Diagram")

        Returns:
            file_token that can be used in image blocks
        """
        # Optionally save image locally
        if save_locally:
            from pathlib import Path
            output_dir = Path(local_dir or "ERD Diagram")
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / filename
            output_path.write_bytes(image_bytes)
            _log.info(f"Saved image locally to {output_path}")

        token = _get_tenant_token(self._app_id, self._app_secret)
        headers = {"Authorization": f"Bearer {token}"}

        # Lark Drive API expects multipart/form-data
        # Use folder_token as parent for better compatibility
        files = {
            "file_name": (None, filename),
            "parent_type": (None, parent_type),
            "parent_node": (None, parent_node if parent_node is not None else self._folder_token),
            "size": (None, str(len(image_bytes))),
            "file": (filename, image_bytes, image_type),
        }

        try:
            resp = _safe_http_request("POST", _LARK_IMAGE_UPLOAD_URL, headers=headers, files=files, timeout=30.0)
            data = resp.json()

            # Check Lark API error code first (they return 200 even on errors)
            if data.get("code", 0) != 0:
                raise RuntimeError(f"Lark image upload failed: {data.get('msg')} (code: {data.get('code')})")

            resp.raise_for_status()

            file_token = data.get("data", {}).get("file_token")
            if not file_token:
                raise RuntimeError(f"Lark image upload returned no file_token: {data}")

            return file_token

        except RuntimeError as e:
            _log.error(f"Failed to upload image '{filename}': {e}")
            raise RuntimeError(f"Image upload failed for '{filename}': {e}")

    def upload_file_to_folder(self, file_bytes: bytes, filename: str, folder_token: str, file_type: str = "image/png") -> str:
        """Upload a file directly to a Lark Drive folder.

        Args:
            file_bytes: Raw file bytes
            filename: Name for the uploaded file
            folder_token: Target folder token
            file_type: MIME type (default: image/png)

        Returns:
            file_token of the uploaded file
        """
        token = _get_tenant_token(self._app_id, self._app_secret)
        headers = {"Authorization": f"Bearer {token}"}

        # Lark Drive API expects multipart/form-data
        files = {
            "file_name": (None, filename),
            "parent_type": (None, "explorer"),
            "parent_node": (None, folder_token),
            "size": (None, str(len(file_bytes))),
            "file": (filename, file_bytes, file_type),
        }

        try:
            resp = _safe_http_request("POST", _LARK_IMAGE_UPLOAD_URL, headers=headers, files=files, timeout=30.0)
            data = resp.json()

            # Check Lark API error code first (they return 200 even on errors)
            if data.get("code", 0) != 0:
                raise RuntimeError(f"Lark file upload failed: {data.get('msg')} (code: {data.get('code')})")

            resp.raise_for_status()

            file_token = data.get("data", {}).get("file_token")
            if not file_token:
                raise RuntimeError(f"Lark file upload returned no file_token: {data}")

            _log.info(f"Uploaded {filename} to folder {folder_token}")
            return file_token

        except RuntimeError as e:
            _log.error(f"Failed to upload file '{filename}' to folder {folder_token}: {e}")
            raise

    def update_erd_page(self, mermaid_erd: str, page_token: str = None, render_as_image: bool = True, replace_existing: bool = True) -> None:
        """Update the ERD in the parent Lark Doc.

        Args:
            mermaid_erd: Mermaid diagram source code
            page_token: Optional Lark Doc ID (uses parent_doc_id if not provided)
            render_as_image: If True, render to PNG and upload as image block. If False, upload as code block.
            replace_existing: If True, replace existing ERD blocks. If False, append new blocks (default: True)
        """
        if not self._parent_doc_id and not page_token:
            _log.warning("No parent document ID provided, skipping ERD update")
            return

        doc_id = page_token or self._parent_doc_id
        token = _get_tenant_token(self._app_id, self._app_secret)
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        # Large ERDs (>5KB) typically fail URL length limits, fall back to code block
        if render_as_image and len(mermaid_erd) <= 5000:
            try:
                from lore.mermaid_renderer import MermaidRenderer
                renderer = MermaidRenderer(format="png")
                image_bytes = renderer.render(mermaid_erd)
                # mermaid.ink returns JPEG despite "png" in URL
                file_token = self._upload_image(image_bytes, image_type="image/jpeg")

                # block_type: 3=heading1, 27=image
                erd_blocks = [
                    {"block_type": 3, "heading1": {"elements": [{"text_run": {"content": "Entity Relationship Diagram"}}]}},
                    {"block_type": 27, "image": {"file_token": file_token}},
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

        # Replace existing ERD blocks if requested
        if replace_existing:
            self._replace_erd_blocks(doc_id, erd_blocks, headers)
        else:
            # Append to end of document (old behavior)
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

        if len(mermaid_erd) <= 5000:
            try:
                image_bytes = MermaidRenderer(format="png").render(mermaid_erd)
                self._insert_doc_image(document_id, image_bytes, headers)
                _log.info("ERD image block appended successfully")
            except Exception as e:
                _log.warning(f"ERD image render failed, skipping image block: {e}")

    def _insert_doc_image(self, document_id: str, image_bytes: bytes, headers: dict) -> None:
        """Append an image to a Lark Doc using the 3-step docx_image flow.

        Step 1: Create empty image block, get its block_id.
        Step 2: Upload bytes with parent_type=docx_image, parent_node=block_id.
        Step 3: Patch the block with the returned file_token.
        """
        block_url = _LARK_DOC_UPDATE_URL.format(document_id=document_id, block_id=document_id)
        resp = httpx.post(block_url, headers=headers, json={
            "children": [{"block_type": 27, "image": {"token": ""}}],
            "index": -1,
        })
        data = resp.json()
        if data.get("code", 0) != 0:
            raise RuntimeError(f"Lark image block create failed: {data.get('msg')}")
        resp.raise_for_status()

        children = data.get("data", {}).get("children", [])
        if not children:
            raise RuntimeError("Lark image block create returned no block_id")
        first = children[0]
        image_block_id = first.get("block_id") if isinstance(first, dict) else first

        file_token = self._upload_image(
            image_bytes,
            image_type="image/jpeg",
            filename="erd.png",
            parent_type="docx_image",
            parent_node=image_block_id,
        )

        patch_url = f"https://open.larksuite.com/open-apis/docx/v1/documents/{document_id}/blocks/{image_block_id}"
        resp = httpx.patch(patch_url, headers=headers, json={"replace_image": {"token": file_token}})
        data = resp.json()
        if data.get("code", 0) != 0:
            raise RuntimeError(f"Lark image block patch failed: {data.get('msg')}")

    def upload_category_erds(self, erd_map: dict[str, str], page_token: str = None, max_categories: int = 20, render_as_image: bool = True, replace: bool = True) -> None:
        """Upload multiple category ERDs to a Lark Doc.

        Args:
            erd_map: Dict mapping category name to Mermaid ERD content
            page_token: Optional Lark Doc ID (uses parent_doc_id if not provided)
            max_categories: Maximum number of categories to upload (to avoid hitting size limits)
            render_as_image: If True, render to PNG and upload as image blocks. If False, upload as code blocks.
            replace: If True, clear document before uploading (default). If False, append to existing content.
        """
        if not self._parent_doc_id and not page_token:
            _log.warning("No parent document ID provided, skipping ERD upload")
            return

        doc_id = page_token or self._parent_doc_id

        # Clear existing content first if replace=True
        if replace:
            _log.info("Clearing existing document content...")
            self._clear_document(doc_id)

        token = _get_tenant_token(self._app_id, self._app_secret)
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        # Build blocks for all categories
        all_blocks = [
            {"block_type": 3, "heading1": {"elements": [{"text_run": {"content": "Schema ERDs by Category"}}]}},
        ]

        # Sort by table count (largest first) and limit to max_categories
        sorted_categories = sorted(erd_map.items(), key=lambda x: x[1].count(" {"), reverse=True)[:max_categories]

        if render_as_image:
            try:
                from lore.mermaid_renderer import MermaidRenderer
                renderer = MermaidRenderer(format="png")
            except ImportError:
                _log.warning("mermaid_renderer not available, falling back to code blocks")
                render_as_image = False

        for category, erd_content in sorted_categories:
            table_count = erd_content.count(" {")
            all_blocks.append({"block_type": 4, "heading2": {"elements": [{"text_run": {"content": f"{category} ({table_count} tables)"}}]}})

            # Try image rendering for smaller ERDs (URL length limit ~5KB)
            if render_as_image and len(erd_content) <= 5000:
                try:
                    image_bytes = renderer.render(erd_content)
                    # mermaid.ink returns JPEG despite "png" in URL
                    file_token = self._upload_image(image_bytes, image_type="image/jpeg")
                    all_blocks.append({"block_type": 27, "image": {"file_token": file_token}})
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

    def upload_individual_category_erds(self, erd_map: dict[str, str], page_token: str = None, as_code: bool = False) -> None:
        """Upload each category ERD individually (one at a time) to a Lark Doc.

        Processes categories one by one without batching, rendering as images where possible.

        Args:
            erd_map: Dict mapping category name to ERD content
            page_token: Optional Lark Doc ID (uses parent_doc_id if not provided)
            as_code: If True, upload all ERDs as code blocks without attempting image rendering
        """
        import time

        if not self._parent_doc_id and not page_token:
            _log.warning("No parent document ID provided, skipping ERD upload")
            return

        doc_id = page_token or self._parent_doc_id
        token = _get_tenant_token(self._app_id, self._app_secret)
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        # Sort categories by name for consistent ordering
        sorted_categories = sorted(erd_map.items())

        uploaded_count = 0
        skipped_count = 0

        for category, erd_content in sorted_categories:
            # Skip categories >15KB (realistic URL length limit for rendering)
            if len(erd_content) > 15000:
                _log.info(f"Skipping {category} ({len(erd_content)} chars, exceeds 15KB limit)")
                skipped_count += 1
                continue

            blocks = []

            # Add category heading
            blocks.append({
                "block_type": 3,
                "heading1": {"elements": [{"text_run": {"content": f"Category: {category}"}}]}
            })

            # Upload as code block (fast, no external service calls)
            if as_code:
                blocks.append({
                    "block_type": 14,
                    "code": {
                        "elements": [{"text_run": {"content": erd_content}}],
                        "style": {"language": 1},
                    }
                })
            else:
                # Try to render as image
                try:
                    from lore.mermaid_renderer import MermaidRenderer
                    renderer = MermaidRenderer(format="png")
                    image_bytes = renderer.render(erd_content)
                    filename = f"{category}.png"
                    file_token = self._upload_image(image_bytes, image_type="image/jpeg", filename=filename, save_locally=True)
                    blocks.append({
                        "block_type": 27,
                        "image": {"file_token": file_token}
                    })
                    _log.info(f"Uploaded {category} as image ({len(erd_content)} chars)")
                except Exception as e:
                    _log.warning(f"Failed to render {category} as image: {e}. Using code block.")
                    blocks.append({
                        "block_type": 14,
                        "code": {
                            "elements": [{"text_run": {"content": erd_content}}],
                            "style": {"language": 1},
                        }
                    })

            # Upload this category's blocks immediately
            block_url = _LARK_DOC_UPDATE_URL.format(document_id=doc_id, block_id=doc_id)
            payload = {
                "children": blocks,
                "index": -1,
            }

            try:
                resp = httpx.post(block_url, headers=headers, json=payload, timeout=60.0)

                if resp.status_code == 403:
                    _log.error(f"403 Forbidden uploading {category}. Bot needs editor access.")
                    skipped_count += 1
                    continue

                resp.raise_for_status()
                data = resp.json()

                if data.get("code", 0) != 0:
                    _log.error(f"Failed to upload {category}: {data.get('msg')} (code: {data.get('code')})")
                    skipped_count += 1
                    continue

                uploaded_count += 1
                # Add delay to avoid rate limiting (Lark API limit: ~20 requests/minute)
                time.sleep(0.5)
            except Exception as e:
                _log.error(f"Failed to upload {category}: {e}")
                skipped_count += 1
                # Add delay even on failure to avoid triggering further rate limits
                time.sleep(1.0)

        _log.info(f"Uploaded {uploaded_count} category ERDs individually (skipped {skipped_count})")

    def upload_erd_files_to_folders(
        self,
        erd_map: dict[str, str],
        image_folder_token: str,
        code_folder_token: str
    ) -> tuple[list[str], list[str]]:
        """Upload ERD files directly to Lark Drive folders (not as documents).

        Args:
            erd_map: Dict mapping category name to ERD content
            image_folder_token: Folder token for PNG files
            code_folder_token: Folder token for Mermaid .mmd files

        Returns:
            Tuple of (uploaded_pngs, uploaded_mmds) lists with filenames
        """
        import time

        if not image_folder_token or not code_folder_token:
            raise ValueError("Both image_folder_token and code_folder_token are required")

        uploaded_pngs = []
        uploaded_mmds = []
        skipped_count = 0

        # Sort categories by name for consistent ordering
        sorted_categories = sorted(erd_map.items())

        for category, erd_content in sorted_categories:
            # Skip oversized ERDs
            if len(erd_content) > 15000:
                _log.info(f"Skipping {category} ({len(erd_content)} chars, exceeds 15KB limit)")
                skipped_count += 1
                continue

            # 1. Upload PNG file to "ERD Diagram" folder (if small enough)
            if len(erd_content) <= 5000:
                try:
                    from lore.mermaid_renderer import MermaidRenderer
                    renderer = MermaidRenderer(format="png")
                    image_bytes = renderer.render(erd_content)
                    filename = f"{category}.png"

                    # Upload PNG file directly to folder
                    file_token = self.upload_file_to_folder(
                        file_bytes=image_bytes,
                        filename=filename,
                        folder_token=image_folder_token,
                        file_type="image/jpeg"
                    )
                    uploaded_pngs.append(filename)
                    _log.info(f"Uploaded PNG: {filename}")

                    time.sleep(0.5)  # Rate limiting

                except Exception as e:
                    _log.error(f"Failed to upload PNG for {category}: {e}")
            else:
                _log.info(f"Skipping PNG for {category} (too large: {len(erd_content)} chars)")

            # 2. Upload .mmd file to "ERD Diagram - Mermaid Code Base" folder
            try:
                filename = f"{category}.mmd"
                mmd_bytes = erd_content.encode('utf-8')

                # Upload .mmd file directly to folder
                file_token = self.upload_file_to_folder(
                    file_bytes=mmd_bytes,
                    filename=filename,
                    folder_token=code_folder_token,
                    file_type="text/plain"
                )
                uploaded_mmds.append(filename)
                _log.info(f"Uploaded .mmd: {filename}")

                time.sleep(0.5)  # Rate limiting

            except Exception as e:
                _log.error(f"Failed to upload .mmd for {category}: {e}")

        _log.info(f"Uploaded {len(uploaded_pngs)} PNG files and {len(uploaded_mmds)} .mmd files (skipped {skipped_count} oversized)")
        return uploaded_pngs, uploaded_mmds
