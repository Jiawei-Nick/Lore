import json
import logging
import anthropic
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
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def _select_model(self, migrations: list[Migration]) -> str:
        if _has_breaking_change(migrations):
            return "claude-sonnet-4-6"
        if _count_changes(migrations) >= 5:
            return "claude-sonnet-4-6"
        return "claude-haiku-4-5-20251001"

    def run(self, context: PipelineContext) -> PipelineContext:
        client = anthropic.Anthropic(api_key=self._api_key)
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
