# ERD Generation Results Summary

Generated category-based ERDs from a 766-table fintech schema.

## Statistics

- **Total tables**: 766
- **Categories**: 130
- **Largest categories**:
  - `wallet`: 170 tables
  - `user`: 81 tables
  - `card`: 70 tables
  - `sales`: 21 tables
  - `cpa`: 19 tables

## Key Findings

### Table Naming Patterns

The schema uses consistent prefixes:
- `tb_<domain>_<entity>`: Main application tables (e.g., `tb_wallet_account`, `tb_user_profile`)
- `mt4_*` / `mt5_*`: MetaTrader integration tables
- `old_tb_*`: Legacy/migrated tables
- `oauth_*`: Authentication tables
- `databasechangelog*`: Liquibase migration tracking

### Relationship Inference Limitations

The FK inference (based on `*_id` → parent table name) has limited effectiveness because:
- Table names use prefixes: `user_id` column doesn't map to a `user` table (it's `tb_user_*`)
- Multi-word entities: `wallet_account_id` would need `wallet_account` table (actual: `tb_wallet_account`)

**Recommendation**: For production use, consider:
1. Parsing actual FOREIGN KEY constraints from `information_schema` during `lore init`
2. Storing FK metadata in `lore-schema.json`
3. Using that metadata for accurate relationship rendering

## Use Cases

### 1. Onboarding New Developers
Point them to the category ERDs for their domain:
- Backend payments team → `erd_payment.mmd`, `erd_wallet.mmd`
- User management → `erd_user.mmd`, `erd_auth.mmd`
- Card services → `erd_card.mmd`

### 2. Schema Documentation
Generate fresh ERDs after schema changes:
```bash
lore init --db postgresql://...
lore generate-erd --output-dir ./docs/erd
```

### 3. Impact Analysis
When planning changes:
1. Check the category ERD for your domain
2. Look at the overview ERD to see which other categories reference yours
3. Grep cross-category comments in related ERDs

## Example Workflow

```bash
# 1. Initialize schema snapshot
lore init --db postgresql://prod-replica/mydb

# 2. Generate all category ERDs
lore generate-erd --output-dir ./docs/erd

# 3. Generate overview
lore generate-erd --output-dir ./docs/erd --overview

# 4. Commit to version control
git add docs/erd/
git commit -m "docs: update schema ERDs"

# 5. View in GitHub/GitLab (auto-renders Mermaid)
# or upload to https://mermaid.live
```

## Future Enhancements

1. **HTML output**: Generate static HTML with clickable category links
2. **FK parsing**: Read actual foreign keys from `information_schema`
3. **Change highlighting**: Show added/modified tables in different colors
4. **Interactive viewer**: Web UI for browsing categories
5. **Lark Docs integration**: Auto-upload category ERDs to Lark Wiki pages
