---
name: add-parser
description: Scaffold a new SQL migration parser in lore/parsers/ following the CompositeParser pattern. Use when adding support for a new migration format (e.g. Atlas, Alembic, TypeORM).
---

When the user asks to add a new parser for a migration format, follow these steps exactly.

## Steps

1. **Create `lore/parsers/<name>.py`**
   - Subclass `ParserPlugin` from `lore/parsers/base.py`
   - Implement `detect_format(filename: str) -> bool` — return `True` for file extensions/patterns this parser owns
   - Implement `parse(raw_diff: str) -> list[MigrationChange]`
   - Import shared helpers from `flyway.py` where applicable: `_FILE_HEADER`, `_ADDED_LINE`, `_parse_statement`
   - Use `Operation`, `MigrationFormat`, `RiskLevel` enum members — never raw strings
   - In f-strings always use `.value`: `f"{op.value}"` not `f"{op}"`

2. **Register in `lore/parsers/composite.py`**
   - Import the new parser class
   - Add an instance to `CompositeParser._parsers` list
   - **This step is the most commonly forgotten — do not skip it**

3. **Create `tests/parsers/test_<name>.py`**
   - Tests use raw unified diff strings constructed inline — no real git repos needed
   - Cover: ADD COLUMN, DROP COLUMN, ALTER TABLE, CREATE TABLE, edge cases (empty diff, unrecognised file, multi-statement)
   - Follow the pattern in `tests/parsers/test_flyway.py`

4. **Run tests**
   ```bash
   python -m pytest tests/parsers/test_<name>.py -v
   ```

## Checklist before finishing
- [ ] `detect_format` filters the correct file extensions/patterns
- [ ] Parser registered in `CompositeParser._parsers`
- [ ] All `Operation`/`RiskLevel` values use enum members, `.value` in f-strings
- [ ] Tests use inline diff strings (no git repos)
- [ ] `python -m pytest tests/parsers/test_<name>.py -v` passes
