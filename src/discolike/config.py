"""Configuration management for DiscoLike CLI."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from discolike.constants import CONFIG_DIR, CONFIG_FILE
from discolike.errors import AuthError


def get_config_dir() -> Path:
    """Get or create the config directory."""
    config_dir = Path(CONFIG_DIR).expanduser()
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_config_path() -> Path:
    """Get the config file path."""
    return get_config_dir() / CONFIG_FILE


def load_config() -> dict[str, Any]:
    """Load config from YAML file."""
    config_path = get_config_path()
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f) or {}
    return {}


def save_config(config: dict[str, Any]) -> None:
    """Save config to YAML file."""
    config_path = get_config_path()
    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False)


def get_api_key() -> str:
    """Get API key from env var or config file. Raises AuthError if not found."""
    # Priority 1: Environment variable
    key = os.environ.get("DISCOLIKE_API_KEY")
    if key:
        return key

    # Priority 2: Config file
    config = load_config()
    raw_key = config.get("api_key")
    config_key: str = str(raw_key) if raw_key else ""
    if config_key:
        return config_key

    raise AuthError("No API key found.")


def mask_key(key: str) -> str:
    """Mask API key for display, showing first 4 and last 4 chars."""
    if len(key) <= 8:
        return "****"
    return f"{key[:4]}...{key[-4:]}"
