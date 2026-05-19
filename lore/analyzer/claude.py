import json
import logging
import os
from anthropic import AnthropicBedrock
from lore.models import Migration, SchemaChange, AnalysisReport, PipelineContext, RiskLevel, Operation

_log = logging.getLogger(__name__)
_BREAKING_OPS = {Operation.DROP, Operation.DROP_TABLE, Operation.ALTER}

_SYSTEM_PROMPT = """You are a database schema change analyst.
Analyze the provided schema changes and return a JSON object with this exact structure:
{
  "summary": "one paragraph describing what changed and why it matters",
  "changes": [],
  "risk_level": "LOW | MEDIUM | HIGH",
  "impact": ["list of affected areas, APIs, or services"],
  "reviewer_notes": "actionable advice for the code reviewer"
}

Risk guidelines:
- LOW: additive changes only (new columns with defaults, new tables)
- MEDIUM: non-breaking alterations, new NOT NULL columns with defaults
- HIGH: DROP operations, type changes, removes NOT NULL constraint, renames

Return only valid JSON. No markdown, no explanation outside the JSON."""


def _count_changes(migrations: list[Migration]) -> int:
    return sum(len(m.changes) for m in migrations)


def _has_breaking_change(migrations: list[Migration]) -> bool:
    return any(c.operation in _BREAKING_OPS for m in migrations for c in m.changes)


class ClaudeAnalyzer:
    def __init__(self, aws_bearer_token: str, aws_region: str = "us-east-1") -> None:
        self._aws_bearer_token = aws_bearer_token
        self._aws_region = aws_region

    def _select_model(self, migrations: list[Migration]) -> str:
        # AWS Bedrock cross-region inference model IDs
        # Using Claude 3.5 Sonnet v2 and Claude 3.5 Haiku
        if _has_breaking_change(migrations):
            return "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
        if _count_changes(migrations) >= 5:
            return "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
        return "us.anthropic.claude-3-5-haiku-20241022-v1:0"

    def run(self, context: PipelineContext) -> PipelineContext:
        # Use the bearer token as api_key for Bedrock
        client = AnthropicBedrock(
            api_key=self._aws_bearer_token,
            aws_region=self._aws_region,
        )
        model = self._select_model(context.migrations)

        changes_payload = [
            {
                "file": m.file,
                "format": m.format,
                "changes": [
                    {"operation": c.operation, "table": c.table, "column": c.column,
                     "data_type": c.data_type, "raw_sql": c.raw_sql}
                    for c in m.changes
                ],
            }
            for m in context.migrations
        ]

        response = client.messages.create(
            model=model,
            max_tokens=1024,
            system=[{"type": "text", "text": _SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": f"Analyze these schema changes:\n{json.dumps(changes_payload, indent=2)}"}],
        )

        try:
            raw = json.loads(response.content[0].text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"Claude returned non-JSON response: {response.content[0].text[:200]}"
            ) from exc
        context.analysis = AnalysisReport(
            summary=raw.get("summary", ""),
            changes=[c for m in context.migrations for c in m.changes],
            risk_level=RiskLevel(raw.get("risk_level", "MEDIUM")),
            impact=raw.get("impact", []),
            reviewer_notes=raw.get("reviewer_notes", ""),
        )
        return context
