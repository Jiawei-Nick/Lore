import os
import pytest
from lore.config import load_config, LoreConfig


def test_load_config_from_dict():
    raw = {
        "aws": {"bearer_token": "test-token", "region": "us-west-2"},
        "lark": {
            "app_id": "app123",
            "app_secret": "secret456",
            "folder_token": "folder789",
            "parent_doc_id": "doc000",
        },
        "repo": {"default_path": "./", "default_branch": "main"},
    }
    config = LoreConfig.from_dict(raw)
    assert config.aws_bearer_token == "test-token"
    assert config.aws_region == "us-west-2"
    assert config.lark_app_id == "app123"
    assert config.lark_folder_token == "folder789"
    assert config.default_branch == "main"


def test_env_var_substitution(monkeypatch):
    monkeypatch.setenv("MY_BEARER_TOKEN", "from-env")
    raw = {
        "aws": {"bearer_token": "${MY_BEARER_TOKEN}", "region": "us-east-1"},
        "lark": {"app_id": "x", "app_secret": "x", "folder_token": "x"},
        "repo": {"default_path": "./", "default_branch": "main"},
    }
    config = LoreConfig.from_dict(raw)
    assert config.aws_bearer_token == "from-env"


def test_missing_required_field_raises():
    with pytest.raises(ValueError, match="lark.app_id"):
        LoreConfig.from_dict({
            "aws": {"bearer_token": "token"},
            "lark": {"app_secret": "x", "folder_token": "x"},
            "repo": {"default_path": "./", "default_branch": "main"},
        })


def test_unset_env_var_raises(monkeypatch):
    monkeypatch.delenv("MISSING_VAR", raising=False)
    raw = {
        "aws": {"bearer_token": "${MISSING_VAR}"},
        "lark": {"app_id": "x", "app_secret": "x", "folder_token": "x"},
        "repo": {"default_path": "./", "default_branch": "main"},
    }
    with pytest.raises(ValueError, match="MISSING_VAR"):
        LoreConfig.from_dict(raw)
