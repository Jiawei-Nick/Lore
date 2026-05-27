import json
import logging
from anthropic import AnthropicBedrock
from lore.models import Migration, AnalysisReport, PipelineContext, RiskLevel, Operation

_log = logging.getLogger(__name__)
_BREAKING_OPS = {Operation.DROP, Operation.DROP_TABLE, Operation.ALTER}

_SYSTEM_PROMPT = """You are a database schema change analyst.
Analyze the provided schema changes and return a JSON object with this exact structure:
{
  "summary": "numbered list by migration script with risk level and paragraph description (format: 1. [RISK] Script_name\\n   Paragraph describing changes\\n\\n2. [RISK] Script_name\\n   Paragraph describing changes)",
  "changes": [],
  "risk_level": "LOW | MEDIUM | HIGH",
  "impact": ["list of affected areas, APIs, or services"],
  "reviewer_notes": "numbered list by migration script with risk level and review notes (format: 1. [RISK] Script_name\\n   Paragraph with review advice\\n\\n2. [RISK] Script_name\\n   Paragraph with review advice)"
}

Risk guidelines:
- LOW: additive changes only (new columns with defaults, new tables, new indexes)
- MEDIUM: non-breaking alterations, new NOT NULL columns with defaults, column type expansions
- HIGH: DROP operations, ALTER/MODIFY column that reduces size or could truncate data (e.g. VARCHAR(50)->VARCHAR(30)), removes NOT NULL constraint, renames, column type changes

Format notes:
- summary: Numbered list (1., 2., etc.) with [RISK_LEVEL] prefix, migration file name, followed by indented paragraph describing what changed
- reviewer_notes: Numbered list (1., 2., etc.) with [RISK_LEVEL] prefix, migration file name, followed by indented paragraph with actionable review advice for that specific script
- Each script should have its own risk assessment (LOW/MEDIUM/HIGH) based on the changes it makes
- Use \\n for line breaks and three spaces for indentation
- Add blank line (\\n\\n) between scripts

Return only valid JSON. No markdown, no explanation outside the JSON."""

_MODEL_SONNET = "global.anthropic.claude-sonnet-4-6"
_MODEL_HAIKU = "global.anthropic.claude-haiku-4-5-20251001-v1:0"


def _count_changes(migrations: list[Migration]) -> int:
    return sum(len(m.changes) for m in migrations)


def _has_breaking_change(migrations: list[Migration]) -> bool:
    return any(c.operation in _BREAKING_OPS for m in migrations for c in m.changes)


class ClaudeAnalyzer:
    def __init__(
        self,
        aws_region: str = "ap-southeast-1",
        aws_access_key_id: str = "",
        aws_secret_access_key: str = "",
        aws_session_token: str = "",
        aws_bearer_token: str = "",
    ) -> None:
        self._aws_region = aws_region
        self._aws_access_key_id = aws_access_key_id
        self._aws_secret_access_key = aws_secret_access_key
        self._aws_session_token = aws_session_token
        self._aws_bearer_token = aws_bearer_token
        # Build client once — reused across run() calls
        self._client = self._build_client()

    def _build_client(self) -> AnthropicBedrock:
        kwargs: dict = {
            "aws_region": self._aws_region,
        }
        # Bearer token takes precedence (if provided)
        if self._aws_bearer_token:
            kwargs["default_headers"] = {
                "Authorization": f"Bearer {self._aws_bearer_token}"
            }
        else:
            # Fall back to key pair or session token
            kwargs["aws_access_key"] = self._aws_access_key_id
            kwargs["aws_secret_key"] = self._aws_secret_access_key
            if self._aws_session_token:
                kwargs["aws_session_token"] = self._aws_session_token
        return AnthropicBedrock(**kwargs)

    def _select_model(self, migrations: list[Migration]) -> str:
        if _has_breaking_change(migrations) or _count_changes(migrations) >= 5:
            return _MODEL_SONNET
        return _MODEL_HAIKU

    def run(self, context: PipelineContext) -> PipelineContext:
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

        response = self._client.messages.create(
            model=model,
            max_tokens=4096,
            system=[{"type": "text", "text": _SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": f"Analyze these schema changes:\n{json.dumps(changes_payload, indent=2)}"}],
        )

        try:
            text = response.content[0].text.strip()
            if text.startswith("```"):
                # Strip opening fence (```json or ```)
                text = text[text.index("\n") + 1:]
                # Strip closing fence
                if "```" in text:
                    text = text[:text.rindex("```")]
                text = text.strip()
            raw = json.loads(text)
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
