import logging
import psycopg2

_log = logging.getLogger(__name__)


def introspect_postgres(db_url: str) -> dict:
    """Connect to PostgreSQL and return full schema as a dict compatible with SchemaStore.tables."""
    conn = psycopg2.connect(db_url)
    schema: dict = {}
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_type = 'BASE TABLE'
                ORDER BY table_name
            """)
            tables = [row[0] for row in cur.fetchall()]

        for table in tables:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = %s
                    ORDER BY ordinal_position
                """, (table,))
                columns = {}
                for col_name, data_type, is_nullable in cur.fetchall():
                    columns[col_name] = {
                        "type": data_type,
                        "nullable": is_nullable == "YES",
                    }
            schema[table] = {"columns": columns}
    finally:
        conn.close()

    return schema
