# lore — AI-Driven Engineering Knowledge Sync Platform
**Date:** 2026-05-17
**Status:** Approved

## Problem

In large systems, database schema changes (tables, columns, indexes) and configuration changes happen frequently, but documentation never keeps up. Teams rely on manual updates to Lark Docs, Excel, and Draw.io — all human-dependent and consistently stale. The result: onboarding friction, repeated cross-team clarification, opaque service dependencies, and missed schema-to-API impact analysis.

## Vision

"Code as Documentation" — lore makes engineering knowledge evolve automatically instead of depending on humans. When a developer triggers an analysis, lore reads the git diff, identifies DB migration changes, uses Claude to analyze impact and risk, and writes a versioned report to Lark Wiki.

---

## Phase 1 Scope

Manual CLI trigger only. GitLab webhook automation is Phase 2.

**In scope:**
- Local git repo as input source
- Auto-detect DB migration format (Flyway, Liquibase, raw DDL)
- Claude-powered schema change analysis
- Lark Wiki output — new child page per run
- `lore init --db <url>` — one-time DB introspection to build schema snapshot + initial ERD
- `lore-schema.json` — local schema snapshot, updated incrementally on each `lore analyze` run
- Mermaid ERD embedded in Lark Wiki parent page, auto-updated on every run

**Out of scope (Phase 2+):**
- GitLab webhook trigger
- Slack / email output
- JPA entity, MyBatis, ORM analysis
- Apollo / Consul config analysis
- Scheduled batch processing

---

## Architecture

### Pipeline (Plugin-based)

```
CLI trigger
    └── Pipeline Runner
          ├── Source Plugin     → extracts raw git diff
          ├── Parser Plugin     → parses migration files into SchemaChange[]
          ├── Claude Analyzer   → produces AnalysisReport
          └── Output Plugin     → writes child page to Lark Wiki
```

Each plugin implements a single `run(context: PipelineContext) -> PipelineContext` method. The `PipelineContext` dataclass carries state through all stages. Adding a new source (e.g., GitLab webhook) or output (e.g., Slack) requires only a new plugin class — the pipeline runner is unchanged.

### Project Structure

```
lore/
├── lore/
│   ├── cli.py                  # Entry point: lore analyze ...
│   ├── pipeline.py             # Orchestrates source → parser → analyzer → output
│   ├── config.py               # Loads lore.yaml (env var substitution)
│   │
│   ├── sources/
│   │   ├── base.py             # SourcePlugin interface
│   │   └── git_local.py        # Extracts diff from local git repo
│   │
│   ├── parsers/
│   │   ├── base.py             # ParserPlugin interface
│   │   ├── detector.py         # Auto-detect migration format
│   │   ├── flyway.py           # Flyway versioned SQL (V{n}__{desc}.sql)
│   │   ├── liquibase.py        # Liquibase XML / YAML / SQL changesets
│   │   └── raw_ddl.py          # Plain DDL scripts
│   │
│   ├── analyzer/
│   │   └── claude.py           # Calls Anthropic API, returns AnalysisReport
│   │
│   └── outputs/
│       ├── base.py             # OutputPlugin interface
│       └── lark.py             # Creates child Wiki page via Lark API
│
├── lore.yaml                   # Config file (see below)
├── pyproject.toml
└── README.md
```

---

## Data Structures

```python
@dataclass
class SchemaChange:
    operation: str        # ADD | DROP | ALTER | CREATE | DROP_TABLE
    table: str
    column: str | None
    data_type: str | None
    raw_sql: str

@dataclass
class Migration:
    file: str             # e.g. V3__add_phone_column.sql
    format: str           # flyway | liquibase | raw_ddl
    changes: list[SchemaChange]

@dataclass
class AnalysisReport:
    summary: str
    changes: list[SchemaChange]  # enriched with Claude's interpretation
    risk_level: str       # LOW | MEDIUM | HIGH
    impact: list[str]     # affected areas (e.g. "User registration flow")
    reviewer_notes: str

@dataclass
class PipelineContext:
    repo_path: str
    branch: str
    raw_diff: str         # populated by source plugin
    migrations: list[Migration]   # populated by parser plugin
    analysis: AnalysisReport | None  # populated by analyzer
    output_url: str | None        # populated by output plugin
```

---

## Claude Analyzer

**Strategy:** structured JSON in, structured JSON out. Claude is called once per pipeline run with all changes batched.

**Prompt caching:** system prompt is cached (static, never changes) — repeated runs on similar repos cost less after the first call.

**Model routing (cost control):**

| Condition | Model |
|---|---|
| < 5 changes | `claude-haiku-4-5` |
| ≥ 5 changes | `claude-sonnet-4-6` |
| Any breaking change detected | `claude-sonnet-4-6` always |

Breaking change detection (pre-Claude, rule-based): DROP TABLE, DROP COLUMN, ALTER COLUMN type change, rename column.

---

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

Environment variables are substituted at load time. No secrets in the config file.

---

## Lark Wiki Output

Each pipeline run creates a **new child page** under the configured parent node.

**Page title format:**
```
{YYYY-MM-DD} | {branch} | {risk_level}
```

**Page content structure:**
```
## Schema Change Report

Branch: feature/add-phone
Date: 2026-05-17
Risk: LOW

### Summary
<Claude-generated summary>

### Changes
| Table | Operation | Column | Type |
|-------|-----------|--------|------|
| user  | ADD       | phone  | VARCHAR(20) |

### Potential Impact
- User registration flow
- Profile API

### Reviewer Notes
<Claude-generated notes>
```

**Result:** Lark Wiki builds a versioned changelog automatically:
```
[Parent] DB Schema Changelog
  └── 2026-05-17 | feature/add-phone | LOW
  └── 2026-05-15 | feature/user-audit | HIGH
  └── 2026-05-10 | fix/remove-legacy | MEDIUM
```

---

## Schema Snapshot & ERD

### lore-schema.json

A local file maintained by lore that tracks the full current schema state. Never committed — add to `.gitignore`.

```json
{
  "version": "1.0",
  "generated_at": "2026-05-17T10:00:00Z",
  "tables": {
    "user": {
      "columns": {
        "id": {"type": "BIGINT", "nullable": false, "primary_key": true},
        "phone": {"type": "VARCHAR(20)", "nullable": true}
      }
    },
    "orders": {
      "columns": {
        "id": {"type": "BIGINT", "nullable": false, "primary_key": true},
        "user_id": {"type": "BIGINT", "nullable": false}
      }
    }
  }
}
```

### lore init (one-time)

Connects to the live DB once to introspect the full schema. Writes `lore-schema.json` and creates the ERD parent page in Lark Wiki.

```bash
lore init --db postgresql://user:pass@host/dbname
```

DB credentials are used only during `lore init`. `lore analyze` never needs DB access.

### lore analyze (incremental updates)

On each run, after parsing migrations:
1. Apply `SchemaChange[]` to `lore-schema.json` (add/drop/alter columns and tables)
2. Re-render Mermaid ERD from updated snapshot
3. Update ERD block on Lark Wiki parent page
4. Create new child page with the change report

### ERD Format (Mermaid)

```
erDiagram
    user {
        BIGINT id PK
        VARCHAR(20) phone
    }
    orders {
        BIGINT id PK
        BIGINT user_id FK
    }
    user ||--o{ orders : "has"
```

Rendered as a live diagram inside the Lark Wiki parent page. Foreign key relationships are inferred from column naming conventions (`*_id` columns → FK to the referenced table if it exists in the schema).

### Lark Wiki Structure

```
[Parent] DB Schema Changelog
  ├── [ERD block — updated on every run]
  ├── 2026-05-17 | feature/add-phone | LOW      ← child page
  ├── 2026-05-15 | feature/user-audit | HIGH     ← child page
  └── 2026-05-10 | fix/remove-legacy | MEDIUM    ← child page
```

## CLI Usage

```bash
# One-time init: introspect DB, build snapshot, create ERD parent page
lore init --db postgresql://user:pass@host/dbname

# Analyze diff between current branch and main
lore analyze --repo ./myapp --branch feature/add-phone

# Override default branch comparison base
lore analyze --repo ./myapp --branch feature/xyz --base develop
```

---

## Phase 2 Roadmap

| Phase | Addition |
|---|---|
| 2 | GitLab webhook source plugin (trigger on PR to release branch) |
| 2 | Slack output plugin |
| 3 | JPA entity + MyBatis mapper analysis |
| 3 | Apollo / Consul config change analysis |
| 4 | AI Knowledge Graph (cross-service impact) |
| 4 | AI Q&A over accumulated lore Wiki |

---

## Security

- Only schema metadata is sent to Claude — no row data, no secrets
- Tokens/secrets in config are env var references, never literal values
- Lark API credentials scoped to Wiki write only
- No raw diff data persisted after pipeline run completes
