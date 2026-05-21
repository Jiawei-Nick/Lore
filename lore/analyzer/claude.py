import json
import logging
from anthropic import AnthropicBedrock
from lore.models import Migration, AnalysisReport, PipelineContext, RiskLevel, Operation

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

# Bedrock cross-region inference profile prefixes by region family.
# ap-* regions use "ap." prefix; us-* regions use "us." prefix.
_REGION_PREFIX = {
    "ap": "ap",
    "us": "us",
    "eu": "eu",
}


def _bedrock_model_prefix(region: str) -> str:
    family = region.split("-")[0]
    return _REGION_PREFIX.get(family, "us")


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
    ) -> None:
        self._aws_region = aws_region
        self._aws_access_key_id = aws_access_key_id
        self._aws_secret_access_key = aws_secret_access_key
        self._aws_session_token = aws_session_token
        # Build client once — reused across run() calls
        self._client = self._build_client()

    def _build_client(self) -> AnthropicBedrock:
        kwargs: dict = {
            "aws_access_key": self._aws_access_key_id,
            "aws_secret_key": self._aws_secret_access_key,
            "aws_region": self._aws_region,
        }
        if self._aws_session_token:
            kwargs["aws_session_token"] = self._aws_session_token
        return AnthropicBedrock(**kwargs)

    def _select_model(self, migrations: list[Migration]) -> str:
        prefix = _bedrock_model_prefix(self._aws_region)
        if _has_breaking_change(migrations) or _count_changes(migrations) >= 5:
            return f"{prefix}.anthropic.claude-3-5-sonnet-20241022-v2:0"
        return f"{prefix}.anthropic.claude-3-5-haiku-20241022-v1:0"

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
