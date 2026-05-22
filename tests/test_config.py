import pytest
from lore.config import load_config, LoreConfig


def test_load_config_from_dict():
    raw = {
        "aws": {"access_key_id": "test-key", "secret_access_key": "test-secret", "region": "us-west-2"},
        "lark": {
            "app_id": "app123",
            "app_secret": "secret456",
            "folder_token": "folder789",
            "parent_doc_id": "doc000",
        },
        "repo": {"default_path": "./", "default_branch": "main"},
    }
    config = LoreConfig.from_dict(raw)
    assert config.aws_access_key_id == "test-key"
    assert config.aws_secret_access_key == "test-secret"
    assert config.aws_region == "us-west-2"
    assert config.lark_app_id == "app123"
    assert config.lark_folder_token == "folder789"
    assert config.default_branch == "main"


def test_env_var_substitution(monkeypatch):
    monkeypatch.setenv("MY_ACCESS_KEY", "key-from-env")
    monkeypatch.setenv("MY_SECRET_KEY", "secret-from-env")
    raw = {
        "aws": {"access_key_id": "${MY_ACCESS_KEY}", "secret_access_key": "${MY_SECRET_KEY}", "region": "us-east-1"},
        "lark": {"app_id": "x", "app_secret": "x", "folder_token": "x"},
        "repo": {"default_path": "./", "default_branch": "main"},
    }
    config = LoreConfig.from_dict(raw)
    assert config.aws_access_key_id == "key-from-env"
    assert config.aws_secret_access_key == "secret-from-env"


def test_missing_required_field_raises():
    with pytest.raises(ValueError, match="lark.app_id"):
        LoreConfig.from_dict({
            "aws": {"access_key_id": "key", "secret_access_key": "secret"},
            "lark": {"app_secret": "x", "folder_token": "x"},
            "repo": {"default_path": "./", "default_branch": "main"},
        })


def test_missing_aws_credentials_raises():
    with pytest.raises(ValueError, match="AWS credentials missing"):
        LoreConfig.from_dict({
            "aws": {"region": "us-east-1"},
            "lark": {"app_id": "x", "app_secret": "x", "folder_token": "x"},
            "repo": {"default_path": "./", "default_branch": "main"},
        })


def test_unset_env_var_raises(monkeypatch):
    monkeypatch.delenv("MISSING_LARK_ID", raising=False)
    raw = {
        "aws": {"access_key_id": "key", "secret_access_key": "secret"},
        "lark": {"app_id": "${MISSING_LARK_ID}", "app_secret": "x", "folder_token": "x"},
        "repo": {"default_path": "./", "default_branch": "main"},
    }
    with pytest.raises(ValueError, match="MISSING_LARK_ID"):
        LoreConfig.from_dict(raw)
