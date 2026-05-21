import re
from typing import Optional


def _infer_fk_relationships(tables: dict) -> list[tuple[str, str]]:
    """Return (parent_table, child_table) pairs from *_id column naming convention."""
    relationships = []
    for table_name, table_def in tables.items():
        for col_name in table_def.get("columns", {}):
            if col_name.endswith("_id") and col_name != "id":
                parent = col_name[:-3]  # strip _id
                if parent in tables:
                    relationships.append((parent, table_name))
    return relationships


def _filter_tables_for_erd(tables: dict, modified_tables: Optional[set[str]] = None, max_chars: int = 90000) -> tuple[dict, str]:
    """Filter tables to fit within Lark's character limit.

    Args:
        tables: Full schema dict
        modified_tables: Set of table names that were modified (if any). If provided, only these + related tables are included.
        max_chars: Maximum ERD size in characters (default 90K to leave buffer under 100K limit)

    Returns:
        (filtered_tables_dict, summary_note_string)
    """
    total = len(tables)

    # If modified_tables provided, prioritize those
    if modified_tables:
        # Include modified tables + tables they reference (via FK) + tables that reference them
        related_tables = set(modified_tables)

        # Add parents (tables referenced by modified tables via *_id columns)
        for table_name in modified_tables:
            if table_name in tables:
                for col_name in tables[table_name].get("columns", {}):
                    if col_name.endswith("_id") and col_name != "id":
                        parent = col_name[:-3]
                        if parent in tables:
                            related_tables.add(parent)

        # Add children (tables that reference modified tables)
        for table_name, table_def in tables.items():
            for col_name in table_def.get("columns", {}):
                if col_name.endswith("_id") and col_name != "id":
                    parent = col_name[:-3]
                    if parent in modified_tables:
                        related_tables.add(table_name)

        filtered = {k: v for k, v in tables.items() if k in related_tables}
        note = f"Showing {len(filtered)} of {total} tables (modified tables + related)"
        return filtered, note

    # Otherwise, sample alphabetically until we hit the size limit
    filtered = {}
    for table_name in sorted(tables.keys()):
        filtered[table_name] = tables[table_name]
        test_erd = _generate_erd_content(filtered)
        if len(test_erd) > max_chars:
            # Remove the last table that pushed us over
            filtered.pop(table_name)
            break

    note = f"Showing {len(filtered)} of {total} tables (alphabetically sampled to fit Lark's 100K char limit)"
    return filtered, note


def _generate_erd_content(tables: dict) -> str:
    """Generate ERD diagram content without header comment."""
    lines = ["erDiagram"]

    for table_name, table_def in sorted(tables.items()):
        columns = table_def.get("columns", {})
        lines.append(f"    {table_name} {{")
        for col_name, col_def in columns.items():
            col_type = re.sub(r"[^A-Za-z0-9_]", "_", col_def.get("type", "UNKNOWN"))
            lines.append(f"        {col_type} {col_name}")
        lines.append("    }")

    for parent, child in _infer_fk_relationships(tables):
        lines.append(f'    {parent} ||--o{{ {child} : "has"')

    return "\n".join(lines)


def generate_mermaid_erd(tables: dict, modified_tables: Optional[set[str]] = None) -> str:
    """Generate Mermaid ERD, filtering if needed to fit Lark's 100K character limit.

    Args:
        tables: Full schema dict
        modified_tables: Optional set of table names that were modified. If provided, ERD focuses on these.

    Returns:
        Mermaid ERD string with header comment explaining any filtering
    """
    # Try full ERD first
    full_erd = _generate_erd_content(tables)
    if len(full_erd) <= 90000:
        return full_erd

    # Need to filter
    filtered, note = _filter_tables_for_erd(tables, modified_tables, max_chars=90000)
    erd_content = _generate_erd_content(filtered)

    # Add explanatory comment at the top
    header = f"%% {note}\n"
    return header + erd_content
