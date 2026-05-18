import re


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


def generate_mermaid_erd(tables: dict) -> str:
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
