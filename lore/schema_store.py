import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from lore.models import SchemaChange, Operation

_log = logging.getLogger(__name__)


class SchemaStore:
    def __init__(self, path: str = "lore-schema.json") -> None:
        self._path = Path(path)
        self.tables: dict = {}

    def load(self) -> None:
        if self._path.exists():
            data = json.loads(self._path.read_text())
            self.tables = data.get("tables", {})

    def save(self) -> None:
        data = {
            "version": "1.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "tables": self.tables,
        }
        self._path.write_text(json.dumps(data, indent=2))

    def apply(self, changes: list[SchemaChange]) -> None:
        for change in changes:
            if change.operation == Operation.CREATE:
                if change.table not in self.tables:
                    self.tables[change.table] = {"columns": {}}

            elif change.operation == Operation.DROP_TABLE:
                self.tables.pop(change.table, None)

            elif change.operation == Operation.ADD and change.column:
                if change.table not in self.tables:
                    self.tables[change.table] = {"columns": {}}
                self.tables[change.table]["columns"][change.column] = {
                    "type": change.data_type or "UNKNOWN",
                    "nullable": True,
                }

            elif change.operation == Operation.DROP and change.column:
                if change.table in self.tables:
                    self.tables[change.table]["columns"].pop(change.column, None)

            elif change.operation == Operation.ALTER and change.column and change.data_type:
                if change.table in self.tables:
                    col = self.tables[change.table]["columns"].get(change.column, {})
                    col["type"] = change.data_type
                    self.tables[change.table]["columns"][change.column] = col
