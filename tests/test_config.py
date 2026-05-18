import os
import pytest
from lore.config import load_config, LoreConfig


def test_load_config_from_dict():
    raw = {
        "anthropic": {"api_key": "test-key"},
        "lark": {
            "app_id": "app123",
            "app_secret": "secret456",
            "wiki_space_id": "space789",
            "parent_node_token": "token000",
        },
        "repo": {"default_path": "./", "default_branch": "main"},
    }
    config = LoreConfig.from_dict(raw)
    assert config.anthropic_api_key == "test-key"
    assert config.lark_app_id == "app123"
    assert config.default_branch == "main"


def test_env_var_substitution(monkeypatch):
    monkeypatch.setenv("MY_API_KEY", "from-env")
    raw = {
        "anthropic": {"api_key": "${MY_API_KEY}"},
        "lark": {"app_id": "x", "app_secret": "x", "wiki_space_id": "x", "parent_node_token": "x"},
        "repo": {"default_path": "./", "default_branch": "main"},
    }
    config = LoreConfig.from_dict(raw)
    assert config.anthropic_api_key == "from-env"


def test_missing_required_field_raises():
    with pytest.raises(ValueError, match="lark.app_id"):
        LoreConfig.from_dict({
            "anthropic": {"api_key": "key"},
            "lark": {"app_secret": "x", "wiki_space_id": "x", "parent_node_token": "x"},
            "repo": {"default_path": "./", "default_branch": "main"},
        })
