import os
import re
from dataclasses import dataclass
from pathlib import Path
import yaml


def _substitute_env_vars(value: str) -> str:
    result = re.sub(r"\$\{(\w+)\}", lambda m: os.environ.get(m.group(1), m.group(0)), value)
    unresolved = re.findall(r"\$\{(\w+)\}", result)
    if unresolved:
        raise ValueError(f"Environment variable(s) not set: {', '.join(unresolved)}")
    return result


def _resolve(d: dict, key: str, *, required: bool = True) -> str:
    parts = key.split(".")
    node = d
    for part in parts:
        if not isinstance(node, dict) or part not in node:
            if required:
                raise ValueError(f"Missing required config key: {key}")
            return ""
        node = node[part]
    return _substitute_env_vars(str(node))


@dataclass
class LoreConfig:
    aws_bearer_token: str
    aws_region: str
    lark_app_id: str
    lark_app_secret: str
    lark_folder_token: str
    lark_parent_doc_id: str
    default_path: str
    default_branch: str

    @classmethod
    def from_dict(cls, raw: dict) -> "LoreConfig":
        return cls(
            aws_bearer_token=_resolve(raw, "aws.bearer_token"),
            aws_region=_resolve(raw, "aws.region", required=False) or "us-east-1",
            lark_app_id=_resolve(raw, "lark.app_id"),
            lark_app_secret=_resolve(raw, "lark.app_secret"),
            lark_folder_token=_resolve(raw, "lark.folder_token"),
            lark_parent_doc_id=_resolve(raw, "lark.parent_doc_id", required=False),
            default_path=_resolve(raw, "repo.default_path", required=False) or "./",
            default_branch=_resolve(raw, "repo.default_branch", required=False) or "main",
        )


def load_config(path: str = "lore.yaml") -> LoreConfig:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with config_path.open() as f:
        raw = yaml.safe_load(f)
    return LoreConfig.from_dict(raw)
