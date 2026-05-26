"""Generate category-based ERD diagrams from schema."""
import re
from typing import Optional
from collections import defaultdict


def _categorize_tables(tables: dict) -> dict[str, list[str]]:
    """Group tables by prefix pattern (e.g., tb_wallet_*, tb_user_*, etc.).

    Returns:
        Dict mapping category name to list of table names
    """
    categories = defaultdict(list)

    for table_name in tables.keys():
        # Extract category from table name prefix
        if table_name.startswith("tb_"):
            # tb_wallet_account → wallet
            parts = table_name.split("_")
            if len(parts) >= 2:
                category = parts[1]
            else:
                category = "other"
        elif table_name.startswith("old_tb_"):
            category = "legacy"
        elif table_name.startswith("mt4_"):
            category = "mt4"
        elif table_name.startswith("mt5_"):
            category = "mt5"
        elif table_name.startswith("oauth_"):
            category = "oauth"
        elif table_name.startswith("database"):
            category = "liquibase"
        else:
            category = "other"

        categories[category].append(table_name)

    return dict(categories)


def _infer_fk_relationships(tables: dict, table_subset: set[str]) -> list[tuple[str, str]]:
    """Return (parent_table, child_table) pairs within the given subset.

    Only returns relationships where both parent and child are in table_subset.
    Intelligently matches columns ending in _id to tables with various naming patterns.
    """
    relationships = []
    for table_name in table_subset:
        if table_name not in tables:
            continue
        table_def = tables[table_name]
        for col_name in table_def.get("columns", {}):
            if col_name.endswith("_id") and col_name != "id":
                parent_base = col_name[:-3]  # strip _id (e.g., "user" from "user_id")

                # Try multiple naming patterns to find parent table
                candidates = [
                    parent_base,  # exact: user_id → user
                    f"tb_{parent_base}",  # prefixed: user_id → tb_user
                    f"tb_{table_name.split('_')[1]}_{parent_base}",  # same category: package_id in tb_commission_* → tb_commission_package
                ]

                # Also check if any table name ends with the parent_base
                for potential_parent in table_subset:
                    if potential_parent.endswith(f"_{parent_base}") or potential_parent.endswith(parent_base):
                        candidates.append(potential_parent)

                # Find first matching candidate
                for candidate in candidates:
                    if candidate in table_subset and candidate != table_name:
                        relationships.append((candidate, table_name))
                        break  # Only add one relationship per column
    return relationships


def _infer_cross_category_relationships(tables: dict, category_tables: set[str]) -> list[tuple[str, str]]:
    """Return (parent_table, child_table) pairs that cross category boundaries.

    Returns relationships where child is in category_tables but parent is in a different category.
    """
    relationships = []
    all_tables = set(tables.keys())

    for table_name in category_tables:
        if table_name not in tables:
            continue
        table_def = tables[table_name]
        for col_name in table_def.get("columns", {}):
            if col_name.endswith("_id") and col_name != "id":
                parent_base = col_name[:-3]

                # Try multiple naming patterns
                candidates = [
                    parent_base,
                    f"tb_{parent_base}",
                ]

                # Also check if any table name ends with the parent_base
                for potential_parent in all_tables:
                    if potential_parent.endswith(f"_{parent_base}") or potential_parent.endswith(parent_base):
                        candidates.append(potential_parent)

                # Find first matching candidate that's NOT in this category
                for candidate in candidates:
                    if candidate in all_tables and candidate not in category_tables and candidate != table_name:
                        relationships.append((candidate, table_name))
                        break
    return relationships


def _generate_erd_for_category(tables: dict, category_name: str, table_names: list[str]) -> str:
    """Generate Mermaid ERD for a single category."""
    table_set = set(table_names)
    lines = [
        f"%% Category: {category_name} ({len(table_names)} tables)",
        "erDiagram",
    ]

    # Add table definitions
    for table_name in sorted(table_names):
        if table_name not in tables:
            continue
        table_def = tables[table_name]
        columns = table_def.get("columns", {})
        lines.append(f"    {table_name} {{")
        for col_name, col_def in columns.items():
            col_type = re.sub(r"[^A-Za-z0-9_]", "_", col_def.get("type", "UNKNOWN"))
            lines.append(f"        {col_type} {col_name}")
        lines.append("    }")

    # Add within-category relationships
    for parent, child in _infer_fk_relationships(tables, table_set):
        lines.append(f'    {parent} ||--o{{ {child} : "has"')

    # Add cross-category relationships (as comments for reference)
    cross_refs = _infer_cross_category_relationships(tables, table_set)
    if cross_refs:
        lines.append("")
        lines.append("    %% Cross-category references:")
        for parent, child in cross_refs:
            lines.append(f"    %% {parent} (external) --> {child}")

    return "\n".join(lines)


def generate_categorized_erds(tables: dict, output_dir: str = ".") -> dict[str, str]:
    """Generate separate ERD files for each category.

    Args:
        tables: Full schema dict from SchemaStore
        output_dir: Directory to write ERD files (default: current directory)

    Returns:
        Dict mapping category name to ERD content
    """
    from pathlib import Path

    categories = _categorize_tables(tables)
    erd_map = {}

    # Create subdirectory for mermaid code files
    mermaid_dir = Path(output_dir) / "ERD Diagram - Mermaid Code Base"
    mermaid_dir.mkdir(parents=True, exist_ok=True)

    for category, table_list in sorted(categories.items()):
        if not table_list:
            continue

        erd_content = _generate_erd_for_category(tables, category, table_list)
        erd_map[category] = erd_content

        # Write to file without "erd_" prefix
        output_path = mermaid_dir / f"{category}.mmd"
        output_path.write_text(erd_content)

    return erd_map
