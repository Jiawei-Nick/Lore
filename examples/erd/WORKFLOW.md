# ERD Generation Workflow

## Simple Commands

### 1. Save to Files Only
```bash
# All category ERDs (130 files for 766-table schema)
lore generate-erd --output-dir ./docs/erd

# Just the overview
lore generate-erd --overview --output-dir ./docs/erd
```

### 2. Upload to Lark Only
```bash
# Overview (recommended for large schemas)
lore generate-erd --upload --overview
```

### 3. Both Files + Lark
```bash
# Save all categories to files + upload overview to Lark
lore generate-erd --output-dir ./docs/erd --upload --overview
```

## Typical Workflows

### A. Documentation in Git

For version-controlled schema documentation:

```bash
# 1. Generate all category ERDs
lore generate-erd --output-dir ./docs/erd

# 2. Generate overview
lore generate-erd --overview --output-dir ./docs/erd

# 3. Commit to repo
git add docs/erd/
git commit -m "docs: update schema ERDs"

# Result: Team can view ERDs on GitHub/GitLab (auto-renders Mermaid)
```

### B. Lark Wiki Documentation

For live Lark documentation:

```bash
# Upload overview to Lark parent doc (updates in-place)
lore generate-erd --upload --overview

# Result: https://open.larksuite.com/docx/NOAfdAHu4opRaXxLLmLlxsHfgQc
```

### C. Both (Recommended)

```bash
# Save detailed ERDs to files, upload overview to Lark
lore generate-erd --output-dir ./docs/erd --upload --overview

# Then commit files
git add docs/erd/
git commit -m "docs: update schema ERDs"
```

**Benefits**:
- **Lark**: High-level overview for quick reference
- **Git**: Detailed per-category ERDs for deep dives
- **History**: Git tracks schema evolution over time

## Integration with `lore analyze`

The two commands serve different purposes:

| Command | Purpose | When to Use |
|---------|---------|-------------|
| `lore analyze --branch feature/x` | **Change analysis** - Shows modified tables + related tables in focused ERD | During PR review |
| `lore generate-erd --upload --overview` | **Full schema documentation** - Overview of all categories | After `lore init` or schema changes |

### Complete Workflow

```bash
# 1. Initial setup: snapshot schema
lore init --db postgresql://prod-replica/mydb

# 2. Generate schema documentation
lore generate-erd --output-dir ./docs/erd --upload --overview
git add docs/erd/ lore-schema.json
git commit -m "docs: add schema snapshot and ERDs"

# 3. Developer makes changes on feature branch
git checkout -b feature/add-wallet-fee

# 4. Review changes before merge
lore analyze --branch feature/add-wallet-fee
# → Creates Lark Doc with analysis + focused ERD of modified tables

# 5. After merge, update schema
lore init --db postgresql://prod-replica/mydb
lore generate-erd --output-dir ./docs/erd --upload --overview
git add docs/erd/ lore-schema.json
git commit -m "docs: update schema after wallet fee feature"
```

## Output Examples

### File Output (`--output-dir ./docs/erd`)

```
docs/erd/
├── erd_overview.mmd         (17K - all categories)
├── erd_wallet.mmd           (45K - 170 tables)
├── erd_user.mmd             (28K - 81 tables)
├── erd_card.mmd             (24K - 70 tables)
├── erd_sales.mmd            (7K - 21 tables)
...
└── erd_coupon.mmd           (1.8K - 5 tables)
```

### Lark Upload (`--upload --overview`)

Updates parent document at:
```
https://open.larksuite.com/docx/NOAfdAHu4opRaXxLLmLlxsHfgQc
```

With high-level diagram showing:
- `wallet_domain (170 tables)`
- `user_domain (81 tables)`
- `card_domain (70 tables)`
- ... 127 more categories
- Cross-category relationships

## Tips

1. **Use `--overview` for Lark** - Detailed category ERDs are too large for Lark's 100K limit
2. **Save files to Git** - Track schema evolution over time
3. **Run after schema changes** - Keep documentation in sync with DB
4. **View in GitHub** - Mermaid renders automatically in `.md` files
5. **Link from README** - Add links to category ERDs in your project README
