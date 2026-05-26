"""Tests for database connection management."""
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from lore.connections import ConnectionManager


@pytest.fixture
def temp_connections_file(tmp_path):
    """Provide a temporary connections.yaml file for testing."""
    test_file = tmp_path / "connections.yaml"
    with patch("lore.connections._CONNECTIONS_FILE", test_file):
        yield test_file


def test_mask_password_postgresql():
    """Test password masking for PostgreSQL URLs."""
    url = "postgresql://user:secretpass@localhost:5432/mydb"
    masked = ConnectionManager.mask_password(url)
    assert masked == "postgresql://user:***@localhost:5432/mydb"
    assert "secretpass" not in masked


def test_mask_password_mysql():
    """Test password masking for MySQL URLs."""
    url = "mysql://root:p@ssw0rd@prod.example.com:3306/database"
    masked = ConnectionManager.mask_password(url)
    assert masked == "mysql://root:***@prod.example.com:3306/database"
    assert "p@ssw0rd" not in masked


def test_mask_password_no_password():
    """Test masking when URL has no password."""
    url = "postgresql://user@localhost/mydb"
    masked = ConnectionManager.mask_password(url)
    assert masked == url  # unchanged


def test_add_connection(temp_connections_file):
    """Test adding a new connection."""
    manager = ConnectionManager()
    manager.add("test-db", "postgresql://user:pass@localhost/db", "Test database")

    assert "test-db" in manager.connections
    assert manager.connections["test-db"]["url"] == "postgresql://user:pass@localhost/db"
    assert manager.connections["test-db"]["description"] == "Test database"


def test_remove_connection(temp_connections_file):
    """Test removing a connection."""
    manager = ConnectionManager()
    manager.add("test-db", "postgresql://user:pass@localhost/db")

    removed = manager.remove("test-db")
    assert removed is True
    assert "test-db" not in manager.connections

    # Try removing non-existent connection
    removed = manager.remove("nonexistent")
    assert removed is False


def test_get_connection(temp_connections_file):
    """Test retrieving a connection."""
    manager = ConnectionManager()
    manager.add("test-db", "postgresql://user:pass@localhost/db", "Test")

    profile = manager.get("test-db")
    assert profile is not None
    assert profile["url"] == "postgresql://user:pass@localhost/db"
    assert profile["description"] == "Test"

    # Try getting non-existent connection
    profile = manager.get("nonexistent")
    assert profile is None


def test_list_all_connections(temp_connections_file):
    """Test listing all connections."""
    manager = ConnectionManager()
    manager.add("db1", "postgresql://user:pass@host1/db1")
    manager.add("db2", "mysql://root:pass@host2/db2", "Production")

    connections = manager.list_all()
    assert len(connections) == 2
    assert "db1" in connections
    assert "db2" in connections


def test_persistence(temp_connections_file):
    """Test that connections are saved and loaded from file."""
    # Create and save connections
    manager1 = ConnectionManager()
    manager1.add("test-db", "postgresql://user:pass@localhost/db", "Test")

    # Load in a new manager instance
    manager2 = ConnectionManager()
    assert "test-db" in manager2.connections
    assert manager2.connections["test-db"]["url"] == "postgresql://user:pass@localhost/db"


def test_update_connection(temp_connections_file):
    """Test updating an existing connection."""
    manager = ConnectionManager()
    manager.add("test-db", "postgresql://user:pass@localhost/db", "Old description")

    # Update URL and description
    manager.add("test-db", "postgresql://user:newpass@localhost/db", "New description")

    profile = manager.get("test-db")
    assert profile["url"] == "postgresql://user:newpass@localhost/db"
    assert profile["description"] == "New description"
