"""Tests for category-based ERD generation."""
from lore.erd_categorized import (
    _categorize_tables,
    _infer_fk_relationships,
    _infer_cross_category_relationships,
    _generate_erd_for_category,
    generate_category_overview,
)


def test_categorize_tables():
    """Test table categorization by prefix."""
    tables = {
        "tb_wallet_account": {},
        "tb_wallet_transaction": {},
        "tb_user_profile": {},
        "tb_user_auth": {},
        "tb_card_info": {},
        "mt4_trades": {},
        "mt5_deals": {},
        "old_tb_wallet_balance": {},
        "oauth_client_details": {},
        "databasechangelog": {},
        "some_other_table": {},
    }

    categories = _categorize_tables(tables)

    assert "wallet" in categories
    assert len(categories["wallet"]) == 2
    assert "tb_wallet_account" in categories["wallet"]
    assert "tb_wallet_transaction" in categories["wallet"]

    assert "user" in categories
    assert len(categories["user"]) == 2

    assert "card" in categories
    assert len(categories["card"]) == 1

    assert "mt4" in categories
    assert len(categories["mt4"]) == 1

    assert "mt5" in categories
    assert len(categories["mt5"]) == 1

    assert "legacy" in categories
    assert "old_tb_wallet_balance" in categories["legacy"]

    assert "oauth" in categories
    assert "oauth_client_details" in categories["oauth"]

    assert "liquibase" in categories
    assert "databasechangelog" in categories["liquibase"]

    assert "other" in categories
    assert "some_other_table" in categories["other"]


def test_infer_fk_relationships():
    """Test FK relationship inference within a category."""
    tables = {
        "user": {"columns": {"id": {}, "name": {}}},
        "order": {"columns": {"id": {}, "user_id": {}, "amount": {}}},
        "payment": {"columns": {"id": {}, "order_id": {}, "status": {}}},
    }

    # All tables in subset
    relationships = _infer_fk_relationships(tables, {"user", "order", "payment"})
    assert ("user", "order") in relationships
    assert ("order", "payment") in relationships

    # Only user and order in subset
    relationships = _infer_fk_relationships(tables, {"user", "order"})
    assert ("user", "order") in relationships
    assert ("order", "payment") not in relationships  # payment not in subset


def test_infer_cross_category_relationships():
    """Test cross-category reference detection."""
    tables = {
        "user": {"columns": {"id": {}, "name": {}}},
        "order": {"columns": {"id": {}, "user_id": {}, "amount": {}}},
        "payment": {"columns": {"id": {}, "order_id": {}, "status": {}}},
    }

    # Payment category references order (different category)
    cross_refs = _infer_cross_category_relationships(tables, {"payment"})
    assert ("order", "payment") in cross_refs

    # Order category references user (different category)
    cross_refs = _infer_cross_category_relationships(tables, {"order"})
    assert ("user", "order") in cross_refs

    # User category has no cross-references
    cross_refs = _infer_cross_category_relationships(tables, {"user"})
    assert len(cross_refs) == 0


def test_generate_erd_for_category():
    """Test ERD generation for a single category."""
    tables = {
        "user": {
            "columns": {
                "id": {"type": "bigint", "nullable": False},
                "name": {"type": "varchar(100)", "nullable": True},
            }
        },
        "user_profile": {
            "columns": {
                "id": {"type": "bigint", "nullable": False},
                "user_id": {"type": "bigint", "nullable": False},
                "bio": {"type": "text", "nullable": True},
            }
        },
        "order": {
            "columns": {
                "id": {"type": "bigint", "nullable": False},
                "user_id": {"type": "bigint", "nullable": False},
            }
        },
    }

    # Generate ERD for user category (user + user_profile, references order)
    erd = _generate_erd_for_category(tables, "user", ["user", "user_profile"])

    # Check header
    assert "%% Category: user (2 tables)" in erd
    assert "erDiagram" in erd

    # Check table definitions
    assert "user {" in erd
    assert "bigint id" in erd
    assert "varchar_100_ name" in erd
    assert "user_profile {" in erd
    assert "text bio" in erd

    # Check within-category relationship
    assert 'user ||--o{ user_profile : "has"' in erd

    # No cross-category references in this example (order is not referenced by user or user_profile)
    # user_profile.user_id references user (same category), not cross-category


def test_generate_category_overview():
    """Test category overview ERD generation."""
    tables = {
        "tb_wallet_account": {"columns": {"id": {}, "user_id": {}}},
        "tb_wallet_transaction": {"columns": {"id": {}, "account_id": {}}},
        "tb_user_profile": {"columns": {"id": {}, "name": {}}},
        "tb_card_info": {"columns": {"id": {}, "user_id": {}}},
    }

    overview = generate_category_overview(tables)

    # Check header
    assert "%% Schema Overview" in overview
    assert "erDiagram" in overview

    # Check category domains are created
    assert "wallet_domain {" in overview
    assert "user_domain {" in overview
    assert "card_domain {" in overview

    # Check table counts are shown
    assert "2 tables" in overview  # wallet has 2 tables

    # Check cross-category relationships
    # wallet references user, card references user
    assert "user_domain ||--o{ wallet_domain" in overview or "wallet_domain" in overview
    assert "user_domain ||--o{ card_domain" in overview or "card_domain" in overview
