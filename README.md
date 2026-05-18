# lore

AI-Driven Engineering Knowledge Sync Platform — a CLI that reads local git diffs, detects database migration changes (Flyway, Liquibase, raw DDL), uses Claude to analyze risk and impact, and publishes versioned reports to Lark Docs with a live Mermaid ERD.

## Install

```bash
pip install -e .
```

Requires Python 3.11+.

**Setup environment variables:**

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and fill in your credentials:
   - `ANTHROPIC_API_KEY` - Get from https://console.anthropic.com/
   - `LARK_APP_ID` & `LARK_APP_SECRET` - Create app at https://open.feishu.cn/app
   - `LARK_FOLDER_TOKEN` - From your Lark Drive folder URL (e.g., https://xxx.feishu.cn/drive/folder/[FOLDER_TOKEN])
   - `LARK_PARENT_DOC_ID` - From your parent Lark Doc URL (e.g., https://xxx.feishu.cn/docx/[DOC_ID])

## Usage

```bash
# One-time: introspect a live PostgreSQL DB, write lore-schema.json, create ERD parent page
lore init --db postgresql://user:pass@host/dbname

# Analyze a feature branch against main
lore analyze --repo ./myapp --branch feature/add-phone

# Analyze against a different base branch
lore analyze --repo ./myapp --branch feature/xyz --base develop
```

## Configuration

`lore.yaml` — all secrets are read from environment variables (stored in `.env`):

```yaml
anthropic:
  api_key: ${ANTHROPIC_API_KEY}

lark:
  app_id: ${LARK_APP_ID}
  app_secret: ${LARK_APP_SECRET}
  folder_token: ${LARK_FOLDER_TOKEN}
  parent_doc_id: ${LARK_PARENT_DOC_ID}

repo:
  default_path: ./
  default_branch: main
```

## What it produces

Each `lore analyze` run:
1. Creates a new Lark Doc titled `{date} | {branch} | {risk_level}` with the full change report in the specified folder
2. Updates the Mermaid ERD block in the parent Lark Doc
3. Updates `lore-schema.json` locally (gitignored)

Your Lark Drive folder builds a versioned changelog automatically:
```
[Folder] DB Schema Reports
  ├── [Parent Doc] ERD — updated on every run
  ├── 2026-05-17 | feature/add-phone | LOW
  └── 2026-05-15 | feature/user-audit | HIGH
```

## Supported migration formats

- **Flyway** — `V{n}__{desc}.sql` versioned scripts
- **Liquibase** — XML and YAML changesets
- **Raw DDL** — plain `.sql` files

## Development

```bash
python -m pytest        # run all tests
python -m pytest -v -k "test_name"  # run a single test
```
