# Category-Based ERD Generation

Lore can generate Entity Relationship Diagrams (ERDs) organized by category from your database schema snapshot.

## Why Category-Based ERDs?

Large schemas with hundreds of tables (like the 766-table fintech schema) are overwhelming in a single ERD. Category-based generation:

- **Splits by domain**: Separate ERDs for `wallet`, `user`, `card`, `payment`, etc.
- **Manageable size**: Each category ERD is viewable and fits well in documentation
- **Cross-references**: Shows which tables reference entities in other categories
- **Overview mode**: High-level view of category relationships

## Usage

### Generate all category ERDs (to files)

```bash
lore generate-erd --output-dir ./erd_output
```

This creates one `.mmd` (Mermaid) file per category:

```
erd_output/
├── erd_wallet.mmd      (170 tables)
├── erd_user.mmd        (81 tables)
├── erd_card.mmd        (70 tables)
├── erd_sales.mmd       (21 tables)
├── erd_cpa.mmd         (19 tables)
...
└── erd_coupon.mmd      (5 tables)
```

### Generate category overview

```bash
# Save to file
lore generate-erd --overview --output-dir ./erd_output

# Upload to Lark parent document
lore generate-erd --upload --overview

# Both
lore generate-erd --overview --output-dir ./erd_output --upload
```

This creates/uploads `erd_overview.mmd` showing:
- All categories as high-level entities
- Cross-category relationships (e.g., `wallet_domain` → `user_domain`)

**Note**: For large schemas (100+ tables), only `--overview` works for Lark uploads due to the 100K character limit. Detailed category ERDs are best saved to files.

## Viewing ERDs

Upload `.mmd` files to:
- **Mermaid Live Editor**: https://mermaid.live
- **GitHub/GitLab**: Renders automatically in `.md` files with mermaid code blocks
- **VS Code**: Install Mermaid Preview extension
- **Confluence/Notion**: Use Mermaid plugins

## Categorization Logic

Tables are categorized by prefix:

| Prefix | Category | Example Tables |
|--------|----------|----------------|
| `tb_wallet_*` | wallet | `tb_wallet_account`, `tb_wallet_transaction` |
| `tb_user_*` | user | `tb_user_profile`, `tb_user_auth` |
| `tb_card_*` | card | `tb_card_info`, `tb_card_transaction` |
| `mt4_*` | mt4 | `mt4_trades`, `mt4_users` |
| `mt5_*` | mt5 | `mt5_deals`, `mt5_positions` |
| `old_tb_*` | legacy | `old_tb_wallet_account` |
| `oauth_*` | oauth | `oauth_client_details` |
| `databasechangelog*` | liquibase | Migration tracking tables |

## Examples

### Small Category: Coupon (5 tables)

See [`erd_coupon.mmd`](./erd_coupon.mmd) for a focused ERD showing the coupon domain:
- `tb_coupon` (main coupon definition)
- `tb_coupon_amount` (currency-specific amounts)
- `tb_coupon_condition` (redemption conditions)
- `tb_coupon_paytype` (payment types)

### Overview

See [`erd_overview.mmd`](./erd_overview.mmd) for the category-level view showing 130 domains and their relationships.

## Integration with `lore analyze`

The `lore analyze` command already generates focused ERDs for modified tables:

```bash
lore analyze --branch feature/add-wallet-fee
```

This updates the parent doc with an ERD showing:
- Modified tables (e.g., `tb_wallet_fee`)
- Parent tables (referenced via `*_id` columns)
- Child tables (tables that reference the modified tables)

The `generate-erd` command complements this by providing **full schema documentation** split by category.
