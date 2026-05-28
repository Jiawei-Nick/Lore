# CLAUDE.md

## What this service does

lore is a CLI tool that analyzes SQL migration diffs, routes them through Claude on AWS Bedrock, and publishes structured risk reports and ERD diagrams to Lark Docs/Drive.

## Tech stack

- **Language:** Python 3.11+
- **CLI framework:** Typer
- **AI inference:** Anthropic SDK (`AnthropicBedrock`) via AWS Bedrock
- **SQL parsing:** sqlglot
- **HTTP client:** httpx
- **Git access:** GitPython
- **Config:** PyYAML + python-dotenv
- **DB introspection:** psycopg2-binary (PostgreSQL), pymysql (MySQL)
- **Package:** hatchling (`pyproject.toml`); entry point `lore = "lore.cli:app"`
- **Tests:** pytest

## Commands

```bash
# Setup
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e .                 # editable install required for CLI

# Tests
python -m pytest                                         # all tests
python -m pytest tests/parsers/test_flyway.py -v        # single file
python -m pytest -k "test_parse_add_column" -v          # single test by name

# Local dev — skip live DB using committed snapshot
cp lore-schema.example.json lore-schema.json            # one-time copy

# End-to-end scripts (require .env with AWS + Lark creds)
python scripts/test_run.py           # baseline — haiku path
python scripts/test_run_low.py       # low impact — haiku path
python scripts/test_run_medium.py    # medium impact — sonnet path
python scripts/test_run_high.py      # high impact — sonnet path
```

## Key API surface

All surface is CLI — no HTTP server.

```
lore init --db <url>                          Introspect DB, write lore-schema.json, push ERD to Lark
lore init --db <url> --save-as <name>         Introspect and save connection shortcut
lore init --use <name>                        Use saved connection shortcut
lore init                                     Interactive connection picker (when shortcuts exist)
lore init-parent [--title <title>]            Create Lark Doc owned by bot (when bot can't edit existing)
lore analyze --repo <path> --branch <branch> [--base <base>]
                                              Diff branch, parse migrations, publish risk report + ERD
lore generate-erd [--output-dir <dir>]        Write .mmd files locally (one per category)
lore generate-erd --upload --upload-files     Upload PNG + .mmd to Lark Drive folders (recommended)
lore generate-erd --upload --individual       Upload each category ERD to parent doc one at a time
lore generate-erd --upload [--max-categories N] [--as-code]
                                              Batch upload to parent doc; skip images >15KB
lore setup-erd-folders                        Create "ERD Diagram" + "ERD Diagram - Mermaid Code Base" in Lark Drive
lore setup-erd-folder --parent-folder <tok> --subfolder-name <name> --document-id <id>
                                              Create subfolder and move doc into it
lore connections list
lore connections add <name> --db <url> [--desc <text>]
lore connections edit <name> [--db <url>] [--desc <text>]
lore connections remove <name> [--yes]
```

## Data model

All in `lore/models.py`.

| Class | Fields |
|---|---|
| `SchemaChange` | `operation: Operation`, `table: str`, `column: str\|None`, `data_type: str\|None`, `raw_sql: str` |
| `Migration` | `file: str`, `format: MigrationFormat`, `changes: list[SchemaChange]` |
| `AnalysisReport` | `summary: str`, `changes: list[SchemaChange]`, `risk_level: RiskLevel`, `impact: list[str]`, `reviewer_notes: str` |
| `PipelineContext` | `repo_path`, `branch`, `base`, `raw_diff`, `migrations`, `analysis`, `output_url`, `db_schema_name` |

**Enums** — all `str, Enum` (JSON-serialize as plain strings):
- `Operation`: `ADD`, `DROP`, `ALTER`, `CREATE`, `DROP_TABLE`
- `MigrationFormat`: `flyway`, `liquibase`, `raw_ddl`
- `RiskLevel`: `LOW`, `MEDIUM`, `HIGH`

**Runtime files:**
- `lore-schema.json` — gitignored; written by `SchemaStore.save()` on each `lore analyze`
- `lore-schema.example.json` — committed reference snapshot
- `~/.lore/connections.yaml` — saved connection profiles; passwords stored in plain text, masked in CLI output

## Key modules / directories

| Path | What lives there |
|---|---|
| `lore/cli.py` | Typer app; all CLI commands wired here |
| `lore/pipeline.py` | `Pipeline` — orchestrates source → parser → analyzer → output |
| `lore/models.py` | All dataclasses and enums |
| `lore/config.py` | `LoreConfig` dataclass; `load_config()`; `${ENV_VAR}` substitution; raises on missing required vars |
| `lore/connections.py` | `ConnectionManager`; CRUD on `~/.lore/connections.yaml`; `mask_password()` static method |
| `lore/sources/base.py` | `SourcePlugin` base class |
| `lore/sources/git_local.py` | `GitLocalSource` — populates `context.raw_diff` via GitPython |
| `lore/parsers/base.py` | `ParserPlugin` base class; `run()` calls `parse()` |
| `lore/parsers/composite.py` | `CompositeParser` — runs all three parsers, merges results |
| `lore/parsers/flyway.py` | Flyway SQL parser; exports `_FILE_HEADER`, `_ADDED_LINE`, `_parse_statement` (re-used by `raw_ddl.py`) |
| `lore/parsers/liquibase.py` | Liquibase XML changelog parser |
| `lore/parsers/raw_ddl.py` | Raw DDL parser; imports flyway helpers directly (intentional coupling) |
| `lore/parsers/detector.py` | `detect_format()` — file-type detection; each parser calls this to self-filter |
| `lore/analyzer/claude.py` | `ClaudeAnalyzer` — model routing, `AnthropicBedrock` call, JSON parse |
| `lore/outputs/base.py` | `OutputPlugin` base class |
| `lore/outputs/lark_doc.py` | `LarkDocOutput` — Lark Docs + Drive API; auth, doc create/update, image upload, folder ops |
| `lore/schema_store.py` | `SchemaStore` — load/apply/save `lore-schema.json`; `apply()` handles all `Operation` variants |
| `lore/erd.py` | `generate_mermaid_erd()` — focused ERD for modified tables + related tables from snapshot |
| `lore/erd_categorized.py` | `_categorize_tables()`, `_generate_erd_for_category()` — prefix-grouped `.mmd` files |
| `lore/mermaid_renderer.py` | `MermaidRenderer` — Mermaid → JPEG via mermaid.ink; skips diagrams >5KB |
| `lore/db_introspect.py` | `introspect_database()` — PostgreSQL + MySQL via `information_schema`; auto-detects from URL scheme |
| `tests/` | Mirrors `lore/`; parsers tested with raw diff strings; Claude + Lark tested with mocked clients |
| `scripts/` | `test_run*.py` — e2e runs against live Claude + Lark; require `.env` |

## External dependencies

| Dependency | Purpose | Env vars |
|---|---|---|
| AWS Bedrock | Claude inference | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` (IAM) — or — `AWS_SESSION_TOKEN` (STS/SSO) — or — `AWS_BEARER_TOKEN_BEDROCK` (Bedrock bearer); `AWS_REGION` (default: `ap-southeast-1`) |
| Lark Docs API (`docx/v1`) | Create/update analysis report documents | `LARK_APP_ID`, `LARK_APP_SECRET`, `LARK_PARENT_DOC_ID`, `LARK_BASE_URL` |
| Lark Drive API (`drive/v1`) | Upload image/code files, create folders, move documents | `LARK_FOLDER_TOKEN`, `LARK_ERD_IMAGE_FOLDER`, `LARK_ERD_CODE_FOLDER` |
| mermaid.ink | Render `.mmd` → JPEG (public API, no auth, URL-based) | — |
| PostgreSQL | Schema introspection (`information_schema`) | connection URL passed to `lore init --db` |
| MySQL | Schema introspection (`information_schema`) | connection URL passed to `lore init --db` |

## Constraints / gotchas

- **Lark HTTP-200 errors:** Lark API returns HTTP 200 on failure. Always check `data.get("code", 0) != 0` after every API call — `raise_for_status()` alone is insufficient.
- **Enum f-strings:** `Operation`, `RiskLevel`, `MigrationFormat` are `str, Enum`. Always use `.value` in f-strings — Python 3.14+ renders `f"{RiskLevel.LOW}"` as `"RiskLevel.LOW"`, not `"LOW"`.
- **Model routing thresholds:** `global.anthropic.claude-haiku-4-5-20251001-v1:0` for <5 non-breaking changes; `global.anthropic.claude-sonnet-4-6` for ≥5 changes or any `DROP`, `DROP_TABLE`, or `ALTER` operation.
- **System prompt caching:** Bedrock calls pass `cache_control: {"type": "ephemeral"}` on the system prompt block.
- **Mermaid size guard:** Diagrams >5KB are skipped for mermaid.ink rendering (URL length limit); fall back to code blocks.
- **ERD character limit:** 100K character ceiling per diagram enforced in `lore/erd.py` and `lore/erd_categorized.py`.
- **lore-schema.json is gitignored** — runtime state only. Use `lore-schema.example.json` as local dev reference.
- **lore analyze never touches the DB** — only `lore init` introspects; analyze reads `lore-schema.json`.
- **sqlglot API shape:** `exp.Alter` (not `exp.AlterTable`); actions in `stmt.args["actions"]` as `exp.ColumnDef` (ADD), `exp.Drop` (DROP COLUMN), `exp.AlterColumn` (ALTER COLUMN).
- **base_url must come from config:** `LarkDocOutput` takes `base_url` from `LARK_BASE_URL`. Never hardcode `open.larksuite.com`.
- **Lark image block type:** image blocks use `block_type 27`.
- **AWS auth — exactly one mode at a time:**
  - IAM: `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY`
  - STS/SSO: `AWS_SESSION_TOKEN`
  - Bedrock bearer: `AWS_BEARER_TOKEN_BEDROCK`
- **flyway helpers are shared:** `_FILE_HEADER`, `_ADDED_LINE`, `_parse_statement` in `lore/parsers/flyway.py` are imported directly by `lore/parsers/raw_ddl.py` — this is intentional, not a circular import.
- **lore init also updates Lark ERD:** after writing `lore-schema.json`, `lore init` calls `LarkDocOutput.update_erd_page()`; oversized ERDs are warned and skipped, not raised.

## Commit message style

```
# Branch naming
feat/<short-description>
feat/<ticket-id>-<short-description>
fix/<short-description>
fix/<ticket-id>-<short-description>

# Never commit directly to main — always branch first
git checkout -b feat/<short-description>
git checkout -b fix/<short-description>

# Conventional commits
# Title: max 50 chars, imperative mood, no trailing period
# Body: bullet points — WHAT changed and WHY
# Never commit .env — only .env.example

feat: add Liquibase parser support

- parse changelog XML format into MigrationChange objects
- detect format via file extension in CompositeParser

fix: guard Lark API error responses

- check data.get('code') != 0, not just raise_for_status
- avoids silent failures on HTTP 200 error responses

# Other prefixes (title only; always add body bullets)
chore: update anthropic SDK dependency
refactor: simplify schema store apply logic
test: add flyway rename column test cases
docs: update lore.yaml config example

# Pull Requests
# Target: main
# Title: same as commit title
# Body: summary bullets + test plan
```

## Configuration

```yaml
# lore.yaml
aws:
  access_key_id: ${AWS_ACCESS_KEY_ID}           # IAM mode
  secret_access_key: ${AWS_SECRET_ACCESS_KEY}   # IAM mode
  session_token: ${AWS_SESSION_TOKEN}           # STS/SSO mode
  bearer_token: ${AWS_BEARER_TOKEN_BEDROCK}     # Bedrock bearer mode
  region: ${AWS_REGION}                         # default: ap-southeast-1

lark:
  app_id: ${LARK_APP_ID}
  app_secret: ${LARK_APP_SECRET}
  folder_token: ${LARK_FOLDER_TOKEN}
  parent_doc_id: ${LARK_PARENT_DOC_ID}
  base_url: ${LARK_BASE_URL}                    # tenant hostname; default: open.larksuite.com
  erd_image_folder: ${LARK_ERD_IMAGE_FOLDER}
  erd_code_folder: ${LARK_ERD_CODE_FOLDER}

repo:
  default_path: ./
  default_branch: main
```

## Architecture

```
CLI (lore/cli.py)
  └── Pipeline (lore/pipeline.py)
        ├── SourcePlugin   → context.raw_diff        (lore/sources/git_local.py)
        ├── ParserPlugin   → context.migrations      (lore/parsers/composite.py)
        ├── ClaudeAnalyzer → context.analysis        (lore/analyzer/claude.py)
        └── OutputPlugin   → context.output_url      (lore/outputs/lark_doc.py)

Post-pipeline:
  SchemaStore.apply() + save()  →  lore-schema.json (incremental)
  LarkDocOutput.append_erd_to_doc()  →  focused ERD on analysis sub-page
```

### Adding a new plugin

- Source: subclass `SourcePlugin` in `lore/sources/`, implement `run(context)`.
- Output: subclass `OutputPlugin` in `lore/outputs/`, implement `run(context)`.
- Parser: subclass `ParserPlugin` in `lore/parsers/`, implement `parse(raw_diff)`, add to `CompositeParser._parsers`.

## Claude Code Automations

```
.claude/
├── settings.json                         # hooks: block .env edits, auto-run pytest after source edits
├── agents/
│   ├── lark-integration-reviewer.md      # validates Lark HTTP-200-error handling
│   ├── schema-migration-analyzer.md      # validates pipeline parse→route→serialize end-to-end
│   ├── erd-generator.md                  # implements ERD features (always run before erd-reviewer)
│   └── erd-reviewer.md                   # validates FK inference, type sanitization, size limits
└── skills/
    ├── add-parser/SKILL.md               # /add-parser — scaffold a new migration parser
    └── add-output/SKILL.md               # /add-output — scaffold a new output plugin
```

### Auto-Spawn Rules

```
Change to lore/outputs/lark_doc.py or lore/mermaid_renderer.py
  → lark-integration-reviewer

Change to lore/analyzer/claude.py or lore/models.py or any lore/parsers/*.py
  → schema-migration-analyzer

User asks to add/modify ERD feature
  → erd-generator → erd-reviewer (in sequence)

Change to lore/erd.py or lore/erd_categorized.py or lore/mermaid_renderer.py
  → erd-reviewer

User asks to add a new migration format parser  → /add-parser
User asks to add a new output destination       → /add-output
```

| Agent | Trigger | What it checks |
|---|---|---|
| `lark-integration-reviewer` | Edit to `lark_doc.py` or `mermaid_renderer.py` | HTTP-200 error guards, token handling, image size limits |
| `schema-migration-analyzer` | Edit to `claude.py`, `models.py`, or any parser | Model routing thresholds, enum serialization, parser output shape |
| `erd-generator` | Any ERD feature implementation | FK inference, size limits, type sanitization, dual-folder structure |
| `erd-reviewer` | After `erd-generator`; edit to `erd.py`, `erd_categorized.py`, `mermaid_renderer.py` | FK inference, 100K char limit, 5KB mermaid.ink guard, category grouping |

## Test layout

```
tests/                          mirrors lore/ package structure
  parsers/                      raw diff string fixtures — no live git repo needed
  analyzer/test_claude.py       mocked AnthropicBedrock client
  outputs/test_lark_doc_erd.py  mocked httpx
  outputs/test_lark_upload_files.py
  test_erd.py
  test_erd_categorized.py
  test_mermaid_renderer.py
  test_schema_store.py
  test_pipeline.py
  test_cli.py / test_cli_erd.py
  test_connections.py
  test_db_introspect.py
  test_config.py
  test_models.py
```

### End-to-end scripts

| Script | Operations | Expected model |
|---|---|---|
| `scripts/test_run.py` | CREATE TABLE, ADD COLUMN, DROP COLUMN | haiku |
| `scripts/test_run_low.py` | 2 × CREATE TABLE | haiku |
| `scripts/test_run_medium.py` | CREATE TABLE + 4 × ADD COLUMN + INDEX | sonnet |
| `scripts/test_run_high.py` | DROP TABLE + DROP COLUMNs + ADD COLUMNs | sonnet |

Prerequisites: `.env` populated with AWS + Lark credentials including `LARK_BASE_URL`.
