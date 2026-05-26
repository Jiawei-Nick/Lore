#!/usr/bin/env python
"""
test_run_high.py - high-impact fixture run: DROP TABLE + multiple DROP COLUMN + ALTER ops.

Expected model: claude-sonnet-4-6 (breaking changes present: DROP_TABLE, DROP COLUMN/ALTER)

Usage: python scripts/test_run_high.py
"""
import sys
import time
import shutil
from pathlib import Path
import git

REPO_ROOT = Path(__file__).parent.parent
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "migrations_high"
DEST_DIR = REPO_ROOT / "db" / "migrations"
BRANCH = f"test/fixture-high-{int(time.time())}"

FIXTURE_FILES = [
    "V040__drop_legacy_audit_table.sql",
    "V041__restructure_user_table.sql",
    "V042__drop_deprecated_columns.sql",
]


def main():
    repo = git.Repo(REPO_ROOT)

    print(f"Creating temp branch: {BRANCH}")
    print("Scenario: high impact — DROP TABLE + DROP COLUMNs + ADD COLUMNs across multiple tables")
    print("Expected model routing: sonnet (breaking changes: DROP_TABLE, ALTER with DROP)\n")
    repo.git.checkout("-b", BRANCH)

    try:
        print("Copying fixture migrations...")
        copied = []
        for fname in FIXTURE_FILES:
            src = FIXTURE_DIR / fname
            dst = DEST_DIR / fname
            shutil.copy2(src, dst)
            repo.index.add([str(dst.relative_to(REPO_ROOT))])
            copied.append(dst)

        repo.index.commit("test: add high-impact fixture migrations")
        print(f"Committed {len(copied)} migration files.")

        print("\nRunning lore analyze...\n")
        from lore.cli import app
        from typer.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(app, ["analyze", "--branch", BRANCH, "--repo", str(REPO_ROOT)])
        print(result.output)
        if result.exception:
            import traceback
            traceback.print_exception(type(result.exception), result.exception, result.exception.__traceback__)
            sys.exit(1)

    finally:
        print("\nCleaning up...")
        repo.git.checkout("main")
        try:
            repo.git.branch("-D", BRANCH)
            print(f"Deleted branch {BRANCH}")
        except git.GitCommandError:
            pass
        for dst in [DEST_DIR / f for f in FIXTURE_FILES]:
            if dst.exists():
                dst.unlink()
        print("Done.")


if __name__ == "__main__":
    main()
