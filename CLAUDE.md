# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install in editable mode (required for CLI to work)
pip install -e .

# Run all tests
python -m pytest

# Run a single test file
python -m pytest tests/parsers/test_flyway.py -v

# Run a single test by name
python -m pytest -k "test_parse_add_column" -v

# CLI usage
lore init --db postgresql://user:pass@host/dbname
lore analyze --repo ./myapp --branch feature/add-phone
lore analyze --repo ./myapp --branch feature/xyz --base develop
```

## Architecture

lore is a plugin-based pipeline CLI. Each stage is a class with a `run(context: PipelineContext) -> PipelineContext` method that mutates and returns the shared context object.

```
CLI (cli.py)
  └── Pipeline (pipeline.py)
        ├── SourcePlugin   → populates context.raw_diff
        ├── ParserPlugin   → populates context.migrations
        ├── ClaudeAnalyzer → populates context.analysis
        └── OutputPlugin   → populates context.output_url
```

After the pipeline runs, `SchemaStore.apply()` + `SchemaStore.save()` update `lore-schema.json` incrementally. A second call to `LarkWikiOutput.update_erd_page()` refreshes the Mermaid ERD on the Lark Wiki parent page.

### Key modules

- **`lore/models.py`** — all dataclasses and enums. `Operation`, `MigrationFormat`, `RiskLevel` are `str, Enum` so they JSON-serialize as plain strings. Always use enum members, never raw strings. In f-strings, always use `.value` (Python 3.14+ renders `f"{RiskLevel.LOW}"` as `"RiskLevel.LOW"`, not `"LOW"`).
- **`lore/parsers/`** — three concrete parsers (Flyway, Liquibase, raw DDL) plus `CompositeParser` which runs all three and merges results. Each parser filters its own file types internally using `detect_format`.
- **`lore/parsers/flyway.py`** — shared `_FILE_HEADER`, `_ADDED_LINE`, `_parse_statement` helpers are imported directly by `raw_ddl.py` (intentional).
- **`lore/analyzer/claude.py`** — model routing: `claude-haiku-4-5-20251001` for <5 non-breaking changes, `claude-sonnet-4-6` for ≥5 or any breaking change. Breaking ops: `{Operation.DROP, Operation.DROP_TABLE, Operation.ALTER}`. System prompt is sent with `cache_control: ephemeral` for prompt caching.
- **`lore/outputs/lark.py`** — Lark API returns HTTP 200 even on errors; always check `data.get("code", 0) != 0` in the response body, not just `raise_for_status()`.
- **`lore/schema_store.py`** — `lore-schema.json` is gitignored and updated incrementally on each `lore analyze` run. `lore analyze` never needs DB access after `lore init`.
- **`lore/erd.py`** — Mermaid ERD generated from the schema snapshot. FK relationships inferred from `*_id` columns if the parent table exists in the snapshot. Type strings are sanitized: `VARCHAR(20)` → `VARCHAR_20_`.
- **`lore/config.py`** — loads `lore.yaml`, substitutes `${ENV_VAR}` references, raises on unresolved vars.

### sqlglot API notes

The actual API uses `exp.Alter` (not `exp.AlterTable`). Actions are in `stmt.args["actions"]` — a list of `exp.ColumnDef` (ADD), `exp.Drop` (DROP COLUMN), or `exp.AlterColumn` (ALTER COLUMN).

### Adding a new plugin

- New source: subclass `SourcePlugin` in `lore/sources/`, implement `run(context)`.
- New output: subclass `OutputPlugin` in `lore/outputs/`, implement `run(context)`.
- New parser: subclass `ParserPlugin` in `lore/parsers/`, implement `parse(raw_diff)`, add to `CompositeParser._parsers`.
- The `Pipeline` runner is unchanged for all cases.

## Configuration

```yaml
# lore.yaml
anthropic:
  api_key: ${ANTHROPIC_API_KEY}

lark:
  app_id: ${LARK_APP_ID}
  app_secret: ${LARK_APP_SECRET}
  wiki_space_id: your-space-id
  parent_node_token: your-parent-page-token

repo:
  default_path: ./
  default_branch: main
```

## Test layout

Tests mirror `lore/` package structure under `tests/`. Parsers are tested with raw unified diff strings constructed directly in tests — no real git repos needed. The Claude analyzer and Lark output are tested with mocked HTTP/API clients.
