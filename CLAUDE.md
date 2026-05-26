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

# Connection management — save shortcuts for easy reuse
lore connections add prod-replica --db postgresql://user:pass@host/db --desc "Production read replica"
lore init --use prod-replica                     # Use saved connection
lore init                                        # Interactive menu (if connections exist)
lore connections list                            # List all saved connections
lore connections edit prod-replica --desc "New description"
lore connections remove staging --yes            # Remove connection
# Connections stored in ~/.lore/connections.yaml (passwords masked in CLI output)

# Analyze migrations
lore analyze --repo ./myapp --branch feature/add-phone
lore analyze --repo ./myapp --branch feature/xyz --base develop

# Local testing without a live DB — use the sample schema snapshot
cp lore-schema.example.json lore-schema.json   # copy once, then run analyze normally
# lore-schema.json is gitignored (runtime state); lore-schema.example.json is the committed reference

# Generate category-based ERDs from schema snapshot
lore generate-erd --output-dir ./erd_output              # Save to dual folders: "ERD Diagram - Mermaid Code Base/"

# One-time setup: Create Lark Drive folders for ERD organization
lore setup-erd-folders                                   # Creates "ERD Diagram" and "ERD Diagram - Mermaid Code Base"

# Upload PNG and .mmd files directly to Lark Drive folders (recommended)
lore generate-erd --upload --upload-files                # Uses LARK_ERD_IMAGE_FOLDER and LARK_ERD_CODE_FOLDER from env
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

After the pipeline runs, `SchemaStore.apply()` + `SchemaStore.save()` update `lore-schema.json` incrementally. `LarkDocOutput.append_erd_to_doc()` appends a focused ERD to the analysis sub-page.

### Key modules

- **`lore/models.py`** — all dataclasses and enums. `Operation`, `MigrationFormat`, `RiskLevel` are `str, Enum` so they JSON-serialize as plain strings. Always use enum members, never raw strings. In f-strings, always use `.value` (Python 3.14+ renders `f"{RiskLevel.LOW}"` as `"RiskLevel.LOW"`, not `"LOW"`).
- **`lore/connections.py`** — manages database connection profiles stored in `~/.lore/connections.yaml`. Provides `ConnectionManager` class for CRUD operations (add, list, edit, remove). Passwords are masked in CLI output using `mask_password()` static method. Used by `lore init` for interactive connection selection and `lore connections` subcommands.
- **`lore/parsers/`** — three concrete parsers (Flyway, Liquibase, raw DDL) plus `CompositeParser` which runs all three and merges results. Each parser filters its own file types internally using `detect_format`.
- **`lore/parsers/flyway.py`** — shared `_FILE_HEADER`, `_ADDED_LINE`, `_parse_statement` helpers are imported directly by `raw_ddl.py` (intentional).
- **`lore/analyzer/claude.py`** — model routing: `claude-haiku-4-5-20251001` for <5 non-breaking changes, `claude-sonnet-4-6` for ≥5 or any breaking change. Breaking ops: `{Operation.DROP, Operation.DROP_TABLE, Operation.ALTER}`. System prompt is sent with `cache_control: ephemeral` for prompt caching.
- **`lore/outputs/lark.py`** — Legacy Lark Wiki API (deprecated, replaced by lark_doc.py).
- **`lore/outputs/lark_doc.py`** — Lark Docs API integration. Uploads analysis reports and ERD diagrams. `LarkDocOutput` takes a `base_url` param (tenant hostname from `LARK_BASE_URL`) used to build all doc URLs — do not hardcode `open.larksuite.com`. `upload_erd_files_to_folders()` uploads PNG and .mmd files directly to Lark Drive folders (recommended method). For legacy single-doc uploads, `update_erd_page()` can replace existing ERD sections in parent documents. ERDs are rendered as images when <5KB; larger diagrams use code blocks. Image upload uses block_type 27. API returns HTTP 200 even on errors; always check `data.get("code", 0) != 0` in the response body.
- **`lore/db_introspect.py`** — database introspection for PostgreSQL and MySQL. Auto-detects DB type from connection URL scheme (`postgresql://` or `mysql://`). Uses `information_schema` queries for both. PostgreSQL requires `psycopg2-binary`, MySQL requires `pymysql`.
- **`lore/schema_store.py`** — `lore-schema.json` is gitignored and updated incrementally on each `lore analyze` run. `lore analyze` never needs DB access after `lore init`.
- **`lore/erd.py`** — Mermaid ERD generated from the schema snapshot. FK relationships inferred from `*_id` columns if the parent table exists in the snapshot. Type strings are sanitized: `VARCHAR(20)` → `VARCHAR_20_`. Used by `lore analyze` to show modified tables + related tables.
- **`lore/erd_categorized.py`** — Category-based ERD generator. Groups tables by prefix (`tb_wallet_*` → wallet, `tb_user_*` → user, etc.) and generates separate `.mmd` files per category in dual-folder structure: "ERD Diagram/" for PNGs, "ERD Diagram - Mermaid Code Base/" for .mmd source files. Filenames use clean names without prefixes (e.g., `wallet.mmd`, not `erd_wallet.mmd`). Includes cross-category reference annotations. Used by `lore generate-erd` command for full schema documentation.
- **`lore/mermaid_renderer.py`** — Renders Mermaid diagrams to images (JPEG) using mermaid.ink API. Used by `lore generate-erd --upload` to convert ERDs to images for Lark Docs. Skips rendering for diagrams >5KB (URL length limit). Falls back to code blocks on error.
- **`lore/config.py`** — loads `lore.yaml`, substitutes `${ENV_VAR}` references, raises on unresolved vars. `LoreConfig.lark_base_url` defaults to `open.larksuite.com` if `LARK_BASE_URL` is unset.

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
lark:
  app_id: ${LARK_APP_ID}
  app_secret: ${LARK_APP_SECRET}
  folder_token: ${LARK_FOLDER_TOKEN}
  parent_doc_id: ${LARK_PARENT_DOC_ID}
  base_url: ${LARK_BASE_URL}           # tenant hostname, defaults to open.larksuite.com
  erd_image_folder: ${LARK_ERD_IMAGE_FOLDER}
  erd_code_folder: ${LARK_ERD_CODE_FOLDER}

repo:
  default_path: ./
  default_branch: main
```

## Git Conventions

```bash
# Branch naming
feat/<short-description>
feat/<ticket-id>-<short-description>   # when ticket is known
fix/<short-description>
fix/<ticket-id>-<short-description>    # when ticket is known

# Always create a branch before starting any work — never commit directly to main
git checkout -b feat/<short-description>
git checkout -b fix/<short-description>

# Commit messages — conventional commits
# Title: max 50 chars, imperative mood, no trailing period
# Body: bullet points detailing WHAT changed and WHY (not just what the code does)
# Never commit .env — only .env.example

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

# Pull Requests
# Target: main
# Title: same as commit message title
# Body: summary bullets + test plan
```

## Claude Code Automations

Project-level Claude Code automations live in `.claude/`:

```
.claude/
├── settings.json          # hooks: block .env edits, auto-run pytest after source edits
├── agents/
│   ├── lark-integration-reviewer.md   # validates Lark HTTP-200-error handling
│   ├── schema-migration-analyzer.md   # validates pipeline parse→route→serialize
│   ├── erd-generator.md              # implements ERD features (run before erd-reviewer)
│   └── erd-reviewer.md               # validates ERD generation, FK inference, size limits
└── skills/
    ├── add-parser/SKILL.md   # /add-parser — scaffold a new migration parser
    └── add-output/SKILL.md   # /add-output — scaffold a new output plugin
```

### Auto-Spawn Rules

```
# Agents — dispatched by Claude when the trigger condition is met

Change to lore/outputs/lark_doc.py
  or lore/outputs/lark.py
  or lore/mermaid_renderer.py           → lark-integration-reviewer

Change to lore/analyzer/claude.py
  or lore/models.py (enums)
  or any lore/parsers/*.py              → schema-migration-analyzer

User asks to add/modify ERD feature        → erd-generator → erd-reviewer (in sequence)

Change to lore/erd.py
  or lore/erd_categorized.py
  or lore/mermaid_renderer.py           → erd-reviewer

# Skills — invoked by user or by Claude when the task matches

User asks to add a new migration format parser  → /add-parser
User asks to add a new output destination       → /add-output
```

### When to dispatch each agent

| Agent | Trigger | What it checks |
|---|---|---|
| `lark-integration-reviewer` | Any edit to `lore/outputs/lark_doc.py`, `lark.py`, or `mermaid_renderer.py` | HTTP-200 error guards, token handling, image size limits |
| `schema-migration-analyzer` | Any edit to `claude.py` (model routing), `models.py` (enums), or parsers | Model routing thresholds, enum serialization, parser output shape |
| `erd-generator` | Implementing any ERD feature | Writes ERD code following domain invariants (FK inference, size limits, type sanitization) |
| `erd-reviewer` | After `erd-generator` completes; any edit to `lore/erd.py`, `erd_categorized.py`, or `mermaid_renderer.py` | FK inference, type sanitization, 100K char limit, 5KB mermaid.ink guard, category grouping |

**ERD feature development workflow:**
```
New ERD feature requested → erd-generator (implement) → erd-reviewer (review) → commit
```

### When to invoke each skill

| Skill | When to use |
|---|---|
| `/add-parser` | Adding support for a new SQL migration format (Atlas, Alembic, TypeORM, etc.) |
| `/add-output` | Adding a new documentation target (Confluence, Notion, GitHub Wiki, Slack, etc.) |

## Test layout

Tests mirror `lore/` package structure under `tests/`. Parsers are tested with raw unified diff strings constructed directly in tests — no real git repos needed. The Claude analyzer and Lark output are tested with mocked HTTP/API clients.

### End-to-end test runs

Each script creates a temp branch, commits fixture migrations into `db/migrations/`, runs `lore analyze` (calls Claude, posts doc to Lark, appends focused ERD), then cleans up.

| Script | Fixture set | Operations | Expected model |
|---|---|---|---|
| `scripts/test_run.py` | `migrations/` | CREATE TABLE, ADD COLUMN, DROP COLUMN | haiku |
| `scripts/test_run_low.py` | `migrations_low/` | 2 × CREATE TABLE | haiku |
| `scripts/test_run_medium.py` | `migrations_medium/` | CREATE TABLE + 4 × ADD COLUMN + INDEX | sonnet |
| `scripts/test_run_high.py` | `migrations_high/` | DROP TABLE + DROP COLUMNs + ADD COLUMNs | sonnet |

```bash
python scripts/test_run.py         # baseline
python scripts/test_run_low.py     # low impact — haiku path
python scripts/test_run_medium.py  # medium impact — sonnet path (volume)
python scripts/test_run_high.py    # high impact — sonnet path (breaking ops)
```

Model routing: haiku for <5 non-breaking changes; sonnet for ≥5 changes or any breaking op (`DROP`, `DROP_TABLE`, `ALTER`). Each script prints the expected model at startup so you can verify routing from the output.

Prerequisites: `.env` must be populated (AWS + Lark credentials including `LARK_BASE_URL`).
