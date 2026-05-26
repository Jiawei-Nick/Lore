# lore

AI-Driven Engineering Knowledge Sync Platform — a CLI that reads local git diffs, detects database migration changes (Flyway, Liquibase, raw DDL), uses Claude to analyze risk and impact, and publishes versioned reports to Lark Docs with a live Mermaid ERD.

## Install

```bash
pip install -e .
```

Requires Python 3.11+.

**Setup environment variables:**

Add to your `~/.zshrc` or `~/.bashrc`:

```bash
# Anthropic API (or use AWS Bedrock - see CLAUDE.md)
export ANTHROPIC_API_KEY="your-api-key"

# Lark App Credentials
export LARK_APP_ID="cli_xxxxx"
export LARK_APP_SECRET="your-secret"
export LARK_FOLDER_TOKEN="your-folder-token"
export LARK_PARENT_DOC_ID="your-doc-id"

# Optional: ERD folder organization (get tokens from `lore setup-erd-folders`)
export LARK_ERD_IMAGE_FOLDER="your-image-folder-token"
export LARK_ERD_CODE_FOLDER="your-code-folder-token"
```

**Where to get these:**
- `ANTHROPIC_API_KEY` - https://console.anthropic.com/
- `LARK_APP_ID` & `LARK_APP_SECRET` - https://open.feishu.cn/app
- `LARK_FOLDER_TOKEN` - From Lark Drive folder URL: `https://xxx.feishu.cn/drive/folder/[FOLDER_TOKEN]`
- `LARK_PARENT_DOC_ID` - From Lark Doc URL: `https://xxx.feishu.cn/docx/[DOC_ID]`
- `LARK_ERD_*_FOLDER` - Run `lore setup-erd-folders` to create and get tokens

## Usage

### Schema Analysis

```bash
# One-time: introspect a live PostgreSQL or MySQL DB, write lore-schema.json
lore init --db postgresql://user:pass@host/dbname
lore init --db mysql://user:pass@host:3306/dbname

# Analyze a feature branch against main
lore analyze --repo ./myapp --branch feature/add-phone

# Analyze against a different base branch
lore analyze --repo ./myapp --branch feature/xyz --base develop
```

### ERD Generation

Generate category-based ERD diagrams organized by table prefix:

```bash
# Save ERDs to local files (dual-folder structure)
lore generate-erd --output-dir ./erd_output
# Creates:
#   erd_output/ERD Diagram - Mermaid Code Base/*.mmd (source files)
#   Local PNG files saved when uploading to Lark

# One-time setup: Create Lark Drive folders
lore setup-erd-folders
# Creates two folders in your Lark Drive:
#   - "ERD Diagram" (for PNG images)
#   - "ERD Diagram - Mermaid Code Base" (for .mmd source files)
# Outputs folder tokens to add to your ~/.zshrc

# Upload files to Lark Drive folders (recommended)
lore generate-erd --upload --upload-files
# Uploads:
#   - PNG images → "ERD Diagram" folder
#   - .mmd files → "ERD Diagram - Mermaid Code Base" folder

# Alternative: Create separate Lark Docs (one document per category)
lore generate-erd --upload --separate-docs
# Creates documents with embedded images or code blocks
```

**File naming:** All generated files use clean names without prefixes:
- ✅ `wallet.mmd`, `wallet.png`
- ❌ ~~`erd_wallet.mmd`~~ (old format)

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
