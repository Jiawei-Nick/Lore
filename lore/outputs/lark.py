import logging
from datetime import date
import httpx
from lore.models import PipelineContext
from lore.outputs.base import OutputPlugin

_log = logging.getLogger(__name__)
_LARK_AUTH_URL = "https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal"
_LARK_WIKI_CREATE_URL = "https://open.larksuite.com/open-apis/wiki/v2/spaces/{space_id}/nodes"
_LARK_WIKI_UPDATE_URL = "https://open.larksuite.com/open-apis/wiki/v2/spaces/{space_id}/nodes/{node_token}"


def _get_tenant_token(app_id: str, app_secret: str) -> str:
    resp = httpx.post(_LARK_AUTH_URL, json={"app_id": app_id, "app_secret": app_secret})
    resp.raise_for_status()
    return resp.json()["tenant_access_token"]


class LarkWikiOutput(OutputPlugin):
    def __init__(self, app_id: str, app_secret: str, wiki_space_id: str, parent_node_token: str) -> None:
        self._app_id = app_id
        self._app_secret = app_secret
        self._wiki_space_id = wiki_space_id
        self._parent_node_token = parent_node_token

    def _build_title(self, context: PipelineContext, run_date: date) -> str:
        risk = context.analysis.risk_level.value if context.analysis else "UNKNOWN"
        return f"{run_date.isoformat()} | {context.branch} | {risk}"

    def _build_content(self, context: PipelineContext, run_date: date) -> str:
        report = context.analysis
        if not report:
            return "No analysis available."

        lines = [
            "## Schema Change Report",
            "",
            f"**Branch:** {context.branch}",
            f"**Date:** {run_date.isoformat()}",
            f"**Risk:** {report.risk_level.value}",
            "",
            "### Summary",
            report.summary,
            "",
            "### Changes",
            "| Table | Operation | Column | Type |",
            "|-------|-----------|--------|------|",
        ]
        for change in report.changes:
            lines.append(f"| {change.table} | {change.operation.value} | {change.column or '-'} | {change.data_type or '-'} |")

        lines += ["", "### Potential Impact"]
        for item in report.impact:
            lines.append(f"- {item}")

        lines += ["", "### Reviewer Notes", report.reviewer_notes]
        return "\n".join(lines)

    def run(self, context: PipelineContext) -> PipelineContext:
        run_date = date.today()
        title = self._build_title(context, run_date)
        content = self._build_content(context, run_date)

        token = _get_tenant_token(self._app_id, self._app_secret)
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        url = _LARK_WIKI_CREATE_URL.format(space_id=self._wiki_space_id)
        payload = {
            "obj_type": "wiki",
            "parent_node_token": self._parent_node_token,
            "node_type": "origin",
            "title": title,
            "content": content,
        }
        resp = httpx.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        context.output_url = data["data"]["node"]["url"]
        return context

    def update_erd_page(self, mermaid_erd: str, page_token: str) -> None:
        """Update the ERD block on the Lark Wiki parent page."""
        token = _get_tenant_token(self._app_id, self._app_secret)
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        url = _LARK_WIKI_UPDATE_URL.format(space_id=self._wiki_space_id, node_token=page_token)
        payload = {"content": f"## Entity Relationship Diagram\n\n```mermaid\n{mermaid_erd}\n```"}
        resp = httpx.patch(url, headers=headers, json=payload)
        resp.raise_for_status()
