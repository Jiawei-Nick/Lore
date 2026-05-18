# lore

AI-Driven Engineering Knowledge Sync Platform — a CLI that reads local git diffs, detects database migration changes (Flyway, Liquibase, raw DDL), uses Claude to analyze risk and impact, and publishes versioned reports to Lark Wiki with a live Mermaid ERD.

## Install

```bash
pip install -e .
```

Requires Python 3.11+. Copy `lore.yaml.example` to `lore.yaml` and set the required environment variables.

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

`lore.yaml` — all secrets are read from environment variables:

```yaml
anthropic:
  api_key: ${ANTHROPIC_API_KEY}

lark:
  app_id: ${LARK_APP_ID}
  app_secret: ${LARK_APP_SECRET}
  wiki_space_id: your-wiki-space-id
  parent_node_token: your-parent-page-token

repo:
  default_path: ./
  default_branch: main
```

## What it produces

Each `lore analyze` run:
1. Creates a new Lark Wiki child page titled `{date} | {branch} | {risk_level}` with the full change report
2. Updates the Mermaid ERD block on the parent Wiki page
3. Updates `lore-schema.json` locally (gitignored)

Lark Wiki builds a versioned changelog automatically:
```
[Parent] DB Schema Changelog
  ├── [ERD — updated on every run]
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
