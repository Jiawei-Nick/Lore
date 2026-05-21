import logging
import re
from typing import Optional

_log = logging.getLogger(__name__)


def introspect_database(db_url: str, schema: Optional[str] = None) -> dict:
    """Auto-detect database type from URL and introspect schema.

    Args:
        db_url: Database connection URL (postgresql://... or mysql://... or jdbc:mysql://...)
        schema: Optional schema/database name. Defaults: 'public' for PostgreSQL, auto-detected for MySQL

    Returns:
        Schema dict compatible with SchemaStore.tables

    Raises:
        ValueError: If database type is not supported
    """
    # Strip jdbc: prefix if present
    url = db_url.replace("jdbc:", "", 1) if db_url.startswith("jdbc:") else db_url

    if url.startswith("postgresql://") or url.startswith("postgres://"):
        return introspect_postgres(url, schema or "public")
    elif url.startswith("mysql://"):
        return introspect_mysql(url, schema)
    else:
        raise ValueError(
            f"Unsupported database URL scheme. Expected postgresql://, mysql://, or jdbc:mysql://, got: {db_url.split('://')[0] if '://' in db_url else db_url}"
        )


def introspect_postgres(db_url: str, schema: str = "public") -> dict:
    """Connect to PostgreSQL and return full schema as a dict compatible with SchemaStore.tables."""
    try:
        import psycopg2
    except ImportError:
        raise ImportError("psycopg2 is required for PostgreSQL introspection. Install with: pip install psycopg2-binary")

    conn = psycopg2.connect(db_url)
    result: dict = {}
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = %s
                  AND table_type = 'BASE TABLE'
                ORDER BY table_name
            """, (schema,))
            tables = [row[0] for row in cur.fetchall()]

        for table in tables:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_schema = %s
                      AND table_name = %s
                    ORDER BY ordinal_position
                """, (schema, table))
                columns = {}
                for col_name, data_type, is_nullable in cur.fetchall():
                    columns[col_name] = {
                        "type": data_type,
                        "nullable": is_nullable == "YES",
                    }
            result[table] = {"columns": columns}
    finally:
        conn.close()

    return result


def introspect_mysql(db_url: str, schema: Optional[str] = None) -> dict:
    """Connect to MySQL and return full schema as a dict compatible with SchemaStore.tables.

    Args:
        db_url: MySQL connection URL (mysql://user:pass@host:port/database)
        schema: Optional database name override. If None, extracts from URL path.
    """
    try:
        import pymysql
    except ImportError:
        raise ImportError("pymysql is required for MySQL introspection. Install with: pip install pymysql")

    # Extract database name from URL if not provided
    if not schema:
        match = re.search(r'/([^/]+?)(?:\?|$)', db_url)
        if match:
            schema = match.group(1)
        else:
            raise ValueError("Could not extract database name from MySQL URL. Provide --schema or use mysql://user:pass@host/dbname")

    # Enable SSL by default for MySQL (common in production environments)
    # Can be disabled with useSSL=false in URL
    use_ssl = not ('usessl=false' in db_url.lower() or 'ssl=false' in db_url.lower())

    conn = pymysql.connect(
        host=_extract_host(db_url),
        port=_extract_port(db_url, default=3306),
        user=_extract_user(db_url),
        password=_extract_password(db_url),
        database=schema,
        ssl={'check_hostname': False} if use_ssl else None,
    )
    result: dict = {}
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = %s
                  AND table_type = 'BASE TABLE'
                ORDER BY table_name
            """, (schema,))
            tables = [row[0] for row in cur.fetchall()]

        for table in tables:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT column_name, column_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_schema = %s
                      AND table_name = %s
                    ORDER BY ordinal_position
                """, (schema, table))
                columns = {}
                for col_name, column_type, is_nullable in cur.fetchall():
                    columns[col_name] = {
                        "type": column_type,
                        "nullable": is_nullable == "YES",
                    }
            result[table] = {"columns": columns}
    finally:
        conn.close()

    return result


def _extract_host(url: str) -> str:
    """Extract host from connection URL."""
    match = re.search(r'@([^:/]+)', url)
    return match.group(1) if match else "localhost"


def _extract_port(url: str, default: int) -> int:
    """Extract port from connection URL."""
    match = re.search(r'@[^:/]+:(\d+)', url)
    return int(match.group(1)) if match else default


def _extract_user(url: str) -> str:
    """Extract username from connection URL."""
    match = re.search(r'://([^:@]+):', url)
    if not match:
        raise ValueError("Could not extract username from database URL")
    return match.group(1)


def _extract_password(url: str) -> str:
    """Extract password from connection URL (between ://user: and @host)."""
    match = re.search(r'://[^:]+:([^@]+)@', url)
    return match.group(1) if match else ""


def _extract_ssl(url: str) -> bool:
    """Check if URL has useSSL=true parameter."""
    return 'useSSL=true' in url.lower() or 'ssl=true' in url.lower()
