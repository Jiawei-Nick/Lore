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
    """
    relationships = []
    for table_name in table_subset:
        if table_name not in tables:
            continue
        table_def = tables[table_name]
        for col_name in table_def.get("columns", {}):
            if col_name.endswith("_id") and col_name != "id":
                parent = col_name[:-3]  # strip _id
                if parent in table_subset:
                    relationships.append((parent, table_name))
    return relationships


def _infer_cross_category_relationships(tables: dict, category_tables: set[str]) -> list[tuple[str, str]]:
    """Return (parent_table, child_table) pairs that cross category boundaries.

    Returns relationships where child is in category_tables but parent is in a different category.
    """
    relationships = []
    for table_name in category_tables:
        if table_name not in tables:
            continue
        table_def = tables[table_name]
        for col_name in table_def.get("columns", {}):
            if col_name.endswith("_id") and col_name != "id":
                parent = col_name[:-3]
                # Cross-category: parent exists in schema but not in this category
                if parent in tables and parent not in category_tables:
                    relationships.append((parent, table_name))
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

    for category, table_list in sorted(categories.items()):
        if not table_list:
            continue

        erd_content = _generate_erd_for_category(tables, category, table_list)
        erd_map[category] = erd_content

        # Write to file
        output_path = Path(output_dir) / f"erd_{category}.mmd"
        output_path.write_text(erd_content)

    return erd_map


def generate_category_overview(tables: dict) -> str:
    """Generate a summary ERD showing categories and their relationships.

    Each category is represented as a single entity, with cross-category relationships shown.
    """
    categories = _categorize_tables(tables)

    lines = [
        "%% Schema Overview: Categories and Cross-Category Relationships",
        "erDiagram",
    ]

    # Add category nodes
    for category, table_list in sorted(categories.items()):
        lines.append(f"    {category}_domain {{")
        lines.append(f"        int table_count \"{len(table_list)} tables\"")
        lines.append(f"        string examples \"{', '.join(sorted(table_list)[:3])}...\"")
        lines.append("    }")

    # Track cross-category relationships at the category level
    category_relationships = defaultdict(set)

    for child_category, table_list in categories.items():
        for table_name in table_list:
            if table_name not in tables:
                continue
            table_def = tables[table_name]
            for col_name in table_def.get("columns", {}):
                if col_name.endswith("_id") and col_name != "id":
                    parent = col_name[:-3]
                    if parent in tables:
                        # Find parent's category
                        for parent_category, parent_tables in categories.items():
                            if parent in parent_tables and parent_category != child_category:
                                category_relationships[parent_category].add(child_category)

    # Add category-level relationships
    for parent_cat, child_cats in sorted(category_relationships.items()):
        for child_cat in sorted(child_cats):
            lines.append(f'    {parent_cat}_domain ||--o{{ {child_cat}_domain : "referenced by"')

    return "\n".join(lines)