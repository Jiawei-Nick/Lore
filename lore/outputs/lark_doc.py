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
        """Build Lark Doc blocks (structured content)."""
        report = context.analysis
        if not report:
            return [{"block_type": 1, "text": {"elements": [{"text_run": {"content": "No analysis available."}}]}}]

        blocks = [
            # Heading 1: Schema Change Report
            {
                "block_type": 2,
                "heading1": {
                    "elements": [{"text_run": {"content": "Schema Change Report"}}]
                }
            },
            # Metadata
            {
                "block_type": 1,
                "text": {
                    "elements": [
                        {"text_run": {"content": f"Branch: {context.branch}\n"}},
                        {"text_run": {"content": f"Date: {run_date.isoformat()}\n"}},
                        {"text_run": {"content": f"Risk: ", "text_element_style": {"bold": True}}},
                        {"text_run": {"content": report.risk_level.value}},
                    ]
                }
            },
            # Summary heading
            {
                "block_type": 3,
                "heading2": {
                    "elements": [{"text_run": {"content": "Summary"}}]
                }
            },
            # Summary content
            {
                "block_type": 1,
                "text": {
                    "elements": [{"text_run": {"content": report.summary}}]
                }
            },
            # Changes heading
            {
                "block_type": 3,
                "heading2": {
                    "elements": [{"text_run": {"content": "Changes"}}]
                }
            },
        ]

        # Add table for changes
        if report.changes:
            table_cells = []
            # Header row
            table_cells.append([
                {"text": "Table"},
                {"text": "Operation"},
                {"text": "Column"},
                {"text": "Type"}
            ])
            # Data rows
            for change in report.changes:
                table_cells.append([
                    {"text": change.table},
                    {"text": change.operation.value},
                    {"text": change.column or "-"},
                    {"text": change.data_type or "-"}
                ])

            blocks.append({
                "block_type": 17,
                "table": {
                    "cells": table_cells
                }
            })

        # Impact section
        blocks.append({
            "block_type": 3,
            "heading2": {
                "elements": [{"text_run": {"content": "Potential Impact"}}]
            }
        })

        for item in report.impact:
            blocks.append({
                "block_type": 1,
                "text": {
                    "elements": [{"text_run": {"content": f"• {item}"}}]
                }
            })

        # Reviewer notes
        blocks.extend([
            {
                "block_type": 3,
                "heading2": {
                    "elements": [{"text_run": {"content": "Reviewer Notes"}}]
                }
            },
            {
                "block_type": 1,
                "text": {
                    "elements": [{"text_run": {"content": report.reviewer_notes}}]
                }
            }
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

        # Construct the document URL manually (Lark API doesn't return it in create response)
        url = f"https://open.larksuite.com/docx/{document_id}"

        # Fetch the document to get the root block_id
        doc_get_url = f"{_LARK_DOC_CREATE_URL}/{document_id}"
        resp = httpx.get(doc_get_url, headers=headers)
        resp.raise_for_status()
        data = resp.json()

        if data.get("code", 0) != 0:
            _log.warning(f"Failed to fetch document for block_id: {data.get('msg')}")
            context.output_url = url
            return context

        block_id = data.get("data", {}).get("document", {}).get("block_id")
        if not block_id:
            _log.warning(f"No block_id in document fetch response: {data}")
            context.output_url = url
            return context

        # Add content blocks to the document
        block_url = _LARK_DOC_UPDATE_URL.format(document_id=document_id, block_id=block_id)
        content_payload = {
            "children": blocks,
            "index": 0
        }
        resp = httpx.patch(block_url, headers=headers, json=content_payload)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code", 0) != 0:
            _log.warning(f"Lark doc content update failed: {data.get('msg')}")

        context.output_url = url
        return context

    def update_erd_page(self, mermaid_erd: str, page_token: str = None) -> None:
        """Update the ERD in the parent Lark Doc."""
        if not self._parent_doc_id and not page_token:
            _log.warning("No parent document ID provided, skipping ERD update")
            return

        doc_id = page_token or self._parent_doc_id
        token = _get_tenant_token(self._app_id, self._app_secret)
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        # Create ERD block
        erd_blocks = [
            {
                "block_type": 2,
                "heading1": {
                    "elements": [{"text_run": {"content": "Entity Relationship Diagram"}}]
                }
            },
            {
                "block_type": 19,  # Code block
                "code": {
                    "elements": [{"text_run": {"content": mermaid_erd}}],
                    "language": 1  # Plain text; mermaid rendering may need special handling
                }
            }
        ]

        # Get document structure to find where to append
        # For simplicity, we'll append to the end by getting the document's root block
        url = f"{_LARK_DOC_CREATE_URL}/{doc_id}"
        resp = httpx.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()

        if data.get("code", 0) != 0:
            raise RuntimeError(f"Lark doc get failed: {data.get('msg')}")

        doc_data = data.get("data", {}).get("document", {})
        block_id = doc_data.get("block_id")

        # Append ERD blocks
        block_url = _LARK_DOC_UPDATE_URL.format(document_id=doc_id, block_id=block_id)
        payload = {
            "children": erd_blocks,
            "index": -1  # Append to end
        }
        resp = httpx.patch(block_url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code", 0) != 0:
            raise RuntimeError(f"Lark doc ERD update failed: {data.get('msg')}")
