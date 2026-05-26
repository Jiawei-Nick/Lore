import os
import re
from dataclasses import dataclass
from pathlib import Path
import yaml


def _substitute_env_vars(value: str, *, raise_on_missing: bool = True) -> str:
    """Substitute ${VAR} references. Uses key-presence check (not value truthiness)
    so that variables explicitly set to "" are treated as present, not missing.
    When raise_on_missing=False, unset vars resolve to '' with no error.
    Note: if a value contains multiple ${VAR} refs and raise_on_missing=False,
    all unset vars are replaced with '' and the partial result is returned silently.
    """
    missing = []

    def replacer(m: re.Match) -> str:
        key = m.group(1)
        if key not in os.environ:
            missing.append(key)
            return ""
        return os.environ[key]

    result = re.sub(r"\$\{(\w+)\}", replacer, value)
    if raise_on_missing and missing:
        raise ValueError(f"Environment variable(s) not set: {', '.join(missing)}")
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
    if node is None:
        if required:
            raise ValueError(f"Missing required config key: {key}")
        return ""
    return _substitute_env_vars(str(node), raise_on_missing=required)


@dataclass
class LoreConfig:
    # AWS auth — use ONE of: key pair (IAM), session_token (STS/SSO), OR bearer_token (Bedrock)
    aws_access_key_id: str      # IAM: required. Others: optional
    aws_secret_access_key: str  # IAM: required. Others: optional
    aws_session_token: str      # STS/SSO: required. Others: optional
    aws_bearer_token: str       # Bedrock bearer token: required. Others: optional
    aws_region: str
    lark_app_id: str
    lark_app_secret: str
    lark_folder_token: str
    lark_parent_doc_id: str
    lark_erd_image_folder: str  # Optional: folder for image-rendered ERDs
    lark_erd_code_folder: str   # Optional: folder for code-based ERDs
    default_path: str
    default_branch: str

    @classmethod
    def from_dict(cls, raw: dict) -> "LoreConfig":
        access_key_id = _resolve(raw, "aws.access_key_id", required=False)
        secret_access_key = _resolve(raw, "aws.secret_access_key", required=False)
        session_token = _resolve(raw, "aws.session_token", required=False)
        bearer_token = _resolve(raw, "aws.bearer_token", required=False)

        # Accept either: key pair (IAM), session token (STS/SSO), or bearer token (Bedrock).
        has_key_pair = bool(access_key_id and secret_access_key)
        has_session_token = bool(session_token)
        has_bearer_token = bool(bearer_token)

        if not has_key_pair and not has_session_token and not has_bearer_token:
            raise ValueError(
                "AWS credentials missing. Set one of:\n"
                "  AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY  (IAM long-term key pair)\n"
                "  AWS_SESSION_TOKEN                           (STS/SSO temporary token)\n"
                "  AWS_BEARER_TOKEN_BEDROCK                    (Bedrock bearer token)"
            )

        return cls(
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            aws_session_token=session_token,
            aws_bearer_token=bearer_token,
            aws_region=_resolve(raw, "aws.region", required=False) or "ap-southeast-1",
            lark_app_id=_resolve(raw, "lark.app_id"),
            lark_app_secret=_resolve(raw, "lark.app_secret"),
            lark_folder_token=_resolve(raw, "lark.folder_token"),
            lark_parent_doc_id=_resolve(raw, "lark.parent_doc_id", required=False),
            lark_erd_image_folder=_resolve(raw, "lark.erd_image_folder", required=False),
            lark_erd_code_folder=_resolve(raw, "lark.erd_code_folder", required=False),
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
