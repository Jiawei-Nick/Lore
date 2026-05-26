#!/usr/bin/env python
"""
test_run_medium.py - medium-impact fixture run: 1 CREATE TABLE + 5 ALTER ADD COLUMN + 1 CREATE INDEX.

Expected model: claude-sonnet-4-6 (>=5 changes total)

Usage: python scripts/test_run_medium.py
"""
import sys
import time
import shutil
from pathlib import Path
import git

REPO_ROOT = Path(__file__).parent.parent
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "migrations_medium"
DEST_DIR = REPO_ROOT / "db" / "migrations"
BRANCH = f"test/fixture-medium-{int(time.time())}"

FIXTURE_FILES = [
    "V030__create_payment_table.sql",
    "V031__add_payment_columns.sql",
]


def main():
    repo = git.Repo(REPO_ROOT)

    print(f"Creating temp branch: {BRANCH}")
    print("Scenario: medium impact — 1 CREATE TABLE + 4 ADD COLUMNs + 1 CREATE INDEX")
    print("Expected model routing: sonnet (>=5 changes, all non-breaking)\n")
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

        repo.index.commit("test: add medium-impact fixture migrations")
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
