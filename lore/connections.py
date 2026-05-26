"""Manage database connection profiles."""
import yaml
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import urlparse, urlunparse


_CONNECTIONS_FILE = Path.home() / ".lore" / "connections.yaml"


class ConnectionManager:
    """Manages saved database connection profiles."""

    def __init__(self):
        self.connections: Dict[str, Dict[str, str]] = {}
        self._ensure_config_dir()
        self.load()

    def _ensure_config_dir(self) -> None:
        """Ensure ~/.lore directory exists."""
        _CONNECTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> None:
        """Load connections from ~/.lore/connections.yaml."""
        if _CONNECTIONS_FILE.exists():
            data = yaml.safe_load(_CONNECTIONS_FILE.read_text())
            self.connections = data.get("connections", {}) if data else {}

    def save(self) -> None:
        """Save connections to ~/.lore/connections.yaml."""
        _CONNECTIONS_FILE.write_text(yaml.safe_dump({"connections": self.connections}, default_flow_style=False))

    def add(self, name: str, url: str, description: str = "") -> None:
        """Add or update a connection profile."""
        self.connections[name] = {
            "url": url,
            "description": description
        }
        self.save()

    def remove(self, name: str) -> bool:
        """Remove a connection profile. Returns True if removed, False if not found."""
        if name in self.connections:
            del self.connections[name]
            self.save()
            return True
        return False

    def get(self, name: str) -> Optional[Dict[str, str]]:
        """Get a connection profile by name."""
        return self.connections.get(name)

    def list_all(self) -> Dict[str, Dict[str, str]]:
        """List all connection profiles."""
        return self.connections

    @staticmethod
    def mask_password(url: str) -> str:
        """Mask password in database URL.

        Example:
            postgresql://user:password@host/db -> postgresql://user:***@host/db
        """
        parsed = urlparse(url)
        if parsed.password:
            # Build new netloc with masked password
            netloc = parsed.hostname or ""
            if parsed.port:
                netloc = f"{netloc}:{parsed.port}"
            if parsed.username:
                netloc = f"{parsed.username}:***@{netloc}"

            masked_url = urlunparse((
                parsed.scheme,
                netloc,
                parsed.path,
                parsed.params,
                parsed.query,
                parsed.fragment
            ))
            return masked_url
        return url