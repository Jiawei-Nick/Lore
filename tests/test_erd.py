from lore.erd import generate_mermaid_erd


def test_generates_basic_erd():
    tables = {
        "user": {
            "columns": {
                "id": {"type": "BIGINT", "nullable": False},
                "phone": {"type": "VARCHAR(20)", "nullable": True},
            }
        }
    }
    erd = generate_mermaid_erd(tables)
    assert "erDiagram" in erd
    assert "user" in erd
    assert "BIGINT id" in erd
    assert "VARCHAR_20_ phone" in erd  # ( and ) replaced by _ from regex


def test_infers_foreign_key_relationship():
    tables = {
        "user": {"columns": {"id": {"type": "BIGINT", "nullable": False}}},
        "orders": {
            "columns": {
                "id": {"type": "BIGINT", "nullable": False},
                "user_id": {"type": "BIGINT", "nullable": False},
            }
        },
    }
    erd = generate_mermaid_erd(tables)
    assert "user ||--o{ orders" in erd


def test_empty_tables_returns_minimal_erd():
    erd = generate_mermaid_erd({})
    assert "erDiagram" in erd


def test_no_false_fk_when_table_missing():
    tables = {
        "orders": {
            "columns": {
                "id": {"type": "BIGINT", "nullable": False},
                "account_id": {"type": "BIGINT", "nullable": False},
            }
        }
    }
    # account table doesn't exist — no FK line should appear
    erd = generate_mermaid_erd(tables)
    assert "||--o{" not in erd


def test_modified_tables_filter_applied_on_small_schema():
    """modified_tables filter must be honoured even when schema fits under 90KB."""
    tables = {
        "user": {"columns": {"id": {"type": "BIGINT", "nullable": False}}},
        "orders": {
            "columns": {
                "id": {"type": "BIGINT", "nullable": False},
                "user_id": {"type": "BIGINT", "nullable": False},
            }
        },
        "products": {"columns": {"id": {"type": "BIGINT", "nullable": False}}},
    }
    erd = generate_mermaid_erd(tables, modified_tables={"orders"})
    assert "orders" in erd
    assert "user" in erd      # FK parent of orders via user_id
    assert "products" not in erd  # unrelated table must be excluded


def test_no_modified_tables_returns_full_schema():
    """Without modified_tables, small schema returns all tables."""
    tables = {
        "user": {"columns": {"id": {"type": "BIGINT", "nullable": False}}},
        "products": {"columns": {"id": {"type": "BIGINT", "nullable": False}}},
    }
    erd = generate_mermaid_erd(tables)
    assert "user" in erd
    assert "products" in erd
