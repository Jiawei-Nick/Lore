from unittest.mock import MagicMock, patch
from lore.db_introspect import introspect_postgres


def test_introspect_builds_schema_dict():
    mock_cursor = MagicMock()
    mock_cursor.fetchall.side_effect = [
        [("user",), ("orders",)],
        [
            ("id", "bigint", "NO"),
            ("phone", "character varying", "YES"),
        ],
        [
            ("id", "bigint", "NO"),
            ("user_id", "bigint", "NO"),
        ],
    ]
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    with patch("psycopg2.connect", return_value=mock_conn):
        schema = introspect_postgres("postgresql://user:pass@host/db")

    assert "user" in schema
    assert "orders" in schema
    assert schema["user"]["columns"]["id"]["type"] == "bigint"
    assert schema["user"]["columns"]["phone"]["nullable"] is True
    assert schema["orders"]["columns"]["user_id"]["nullable"] is False
