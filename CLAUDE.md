# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Python 3.11+ required
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install in editable mode (required for CLI to work)
pip install -e .

# Run all tests
python -m pytest

# Run a single test file
python -m pytest tests/parsers/test_flyway.py -v

# Run a single test by name
python -m pytest -k "test_parse_add_column" -v

# CLI usage — supports both PostgreSQL and MySQL
lore init --db postgresql://user:pass@host/dbname
lore init --db mysql://user:pass@host:3306/dbname
lore analyze --repo ./myapp --branch feature/add-phone
lore analyze --repo ./myapp --branch feature/xyz --base develop

# Generate category-based ERDs from schema snapshot
lore generate-erd --output-dir ./erd_output              # Save all categories to files (.mmd)
lore generate-erd --overview --output-dir ./erd_output   # Save overview to file
lore generate-erd --upload --max-categories 5            # Upload top 5 as images to Lark
lore generate-erd --upload --overview                    # Upload overview (code block if >5KB)
lore generate-erd --output-dir ./docs --upload --max-categories 10  # Both file + Lark
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
- **`lore/outputs/lark.py`** — Legacy Lark Wiki API (deprecated, replaced by lark_doc.py).
- **`lore/outputs/lark_doc.py`** — Lark Docs API integration. Uploads analysis reports and ERD diagrams. ERDs are rendered as images (via `mermaid_renderer.py`) when <5KB; larger diagrams use code blocks. Image upload uses block_type 27. API returns HTTP 200 even on errors; always check `data.get("code", 0) != 0` in the response body.
- **`lore/db_introspect.py`** — database introspection for PostgreSQL and MySQL. Auto-detects DB type from connection URL scheme (`postgresql://` or `mysql://`). Uses `information_schema` queries for both. PostgreSQL requires `psycopg2-binary`, MySQL requires `pymysql`.
- **`lore/schema_store.py`** — `lore-schema.json` is gitignored and updated incrementally on each `lore analyze` run. `lore analyze` never needs DB access after `lore init`.
- **`lore/erd.py`** — Mermaid ERD generated from the schema snapshot. FK relationships inferred from `*_id` columns if the parent table exists in the snapshot. Type strings are sanitized: `VARCHAR(20)` → `VARCHAR_20_`. Used by `lore analyze` to show modified tables + related tables.
- **`lore/erd_categorized.py`** — Category-based ERD generator. Groups tables by prefix (`tb_wallet_*` → wallet, `tb_user_*` → user, etc.) and generates separate `.mmd` files per category. Includes cross-category reference annotations. Used by `lore generate-erd` command for full schema documentation.
- **`lore/mermaid_renderer.py`** — Renders Mermaid diagrams to images (JPEG) using mermaid.ink API. Used by `lore generate-erd --upload` to convert ERDs to images for Lark Docs. Skips rendering for diagrams >5KB (URL length limit). Falls back to code blocks on error.
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

## Git Conventions

```bash
# Branch naming
feat/<short-description>
fix/<short-description>

# Commit messages — conventional commits
# Title: max 50 chars, imperative mood, no trailing period
# Body: bullet points detailing what changed and why

"feat: add Liquibase parser support

- parse changelog XML format into MigrationChange objects
- detect format via file extension in CompositeParser"

"fix: guard Lark API error responses

- check data.get('code') != 0, not just raise_for_status
- avoids silent failures on HTTP 200 error responses"

"chore: update anthropic SDK dependency"
"refactor: simplify schema store apply logic"
"test: add flyway rename column test cases"
"docs: update lore.yaml config example"
```

## Test layout

Tests mirror `lore/` package structure under `tests/`. Parsers are tested with raw unified diff strings constructed directly in tests — no real git repos needed. The Claude analyzer and Lark output are tested with mocked HTTP/API clients.
