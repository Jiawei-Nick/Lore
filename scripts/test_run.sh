#!/usr/bin/env bash
# test_run.sh — create a temp branch with fixture migrations, run lore analyze, then clean up
# Usage: bash scripts/test_run.sh

set -e

BRANCH="test/fixture-run-$(date +%s)"
FIXTURE_DIR="tests/fixtures/migrations"
DEST_DIR="db/migrations"

echo "Creating temp branch: $BRANCH"
git checkout -b "$BRANCH"

echo "Copying fixture migrations..."
cp "$FIXTURE_DIR"/*.sql "$DEST_DIR/"
git add "$DEST_DIR"/V010__create_orders_table.sql \
        "$DEST_DIR"/V011__add_order_items.sql \
        "$DEST_DIR"/V012__drop_legacy_column.sql
git commit -m "test: add fixture migrations for lore analyze dry run"

echo ""
echo "Running lore analyze..."
python -c "
import os
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
from lore.cli import app
from typer.testing import CliRunner
r = CliRunner()
result = r.invoke(app, ['analyze', '--branch', '$BRANCH', '--repo', '.'])
print(result.output)
if result.exception:
    import traceback
    traceback.print_exception(type(result.exception), result.exception, result.exception.__traceback__)
"

echo ""
echo "Cleaning up: removing temp branch and migration files..."
git checkout main
git branch -D "$BRANCH"
rm -f "$DEST_DIR/V010__create_orders_table.sql" \
      "$DEST_DIR/V011__add_order_items.sql" \
      "$DEST_DIR/V012__drop_legacy_column.sql"

echo "Done."
