import subprocess
import pytest
from lore.models import PipelineContext
from lore.sources.git_local import GitLocalSource


@pytest.fixture
def git_repo_with_migration(tmp_path):
    """Create a real git repo with a migration file on a feature branch."""
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "test@test.com"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Test"], check=True, capture_output=True)

    # Initial commit on main
    (tmp_path / "README.md").write_text("init")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-m", "init"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "branch", "-m", "main"], check=True, capture_output=True)

    # Feature branch with migration
    subprocess.run(["git", "-C", str(tmp_path), "checkout", "-b", "feature/add-phone"], check=True, capture_output=True)
    migrations = tmp_path / "db" / "migrations"
    migrations.mkdir(parents=True)
    (migrations / "V2__add_phone.sql").write_text("ALTER TABLE user ADD COLUMN phone VARCHAR(20);")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-m", "add phone migration"], check=True, capture_output=True)

    return tmp_path


def test_git_local_extracts_diff(git_repo_with_migration):
    ctx = PipelineContext(repo_path=str(git_repo_with_migration), branch="feature/add-phone", base="main")
    source = GitLocalSource()
    result = source.run(ctx)
    assert "V2__add_phone.sql" in result.raw_diff
    assert "ADD COLUMN phone" in result.raw_diff


def test_git_local_raises_on_invalid_repo(tmp_path):
    ctx = PipelineContext(repo_path=str(tmp_path), branch="main")
    source = GitLocalSource()
    with pytest.raises(ValueError, match="not a git repository"):
        source.run(ctx)


def test_git_local_raises_on_invalid_branch(git_repo_with_migration):
    ctx = PipelineContext(repo_path=str(git_repo_with_migration), branch="nonexistent-branch", base="main")
    source = GitLocalSource()
    with pytest.raises(ValueError, match="Git ref not found"):
        source.run(ctx)
