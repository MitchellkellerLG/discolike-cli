"""Tests for config module."""

from pathlib import Path

import pytest

from discolike.config import get_api_key, load_config, mask_key
from discolike.errors import AuthError


def test_get_api_key_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISCOLIKE_API_KEY", "dk_test_key_123")
    assert get_api_key() == "dk_test_key_123"


def test_get_api_key_from_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("DISCOLIKE_API_KEY", raising=False)
    monkeypatch.setattr("discolike.config.get_config_dir", lambda: tmp_path)
    monkeypatch.setattr("discolike.config.get_config_path", lambda: tmp_path / "config.yaml")
    save_config_to = tmp_path / "config.yaml"
    save_config_to.write_text("api_key: dk_from_config_456\n")
    # Need to patch the load path too
    monkeypatch.setattr("discolike.config.get_config_path", lambda: save_config_to)
    assert get_api_key() == "dk_from_config_456"


def test_get_api_key_missing_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("DISCOLIKE_API_KEY", raising=False)
    monkeypatch.setattr("discolike.config.get_config_path", lambda: tmp_path / "config.yaml")
    with pytest.raises(AuthError):
        get_api_key()


def test_env_var_takes_priority_over_config(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("DISCOLIKE_API_KEY", "dk_env_key")
    config_file = tmp_path / "config.yaml"
    config_file.write_text("api_key: dk_config_key\n")
    monkeypatch.setattr("discolike.config.get_config_path", lambda: config_file)
    assert get_api_key() == "dk_env_key"


def test_save_and_load_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("discolike.config.get_config_path", lambda: tmp_path / "config.yaml")
    monkeypatch.setattr("discolike.config.get_config_dir", lambda: tmp_path)
    from discolike.config import save_config as sc
    sc({"api_key": "dk_test", "default_country": "US"})
    loaded = load_config()
    assert loaded["api_key"] == "dk_test"
    assert loaded["default_country"] == "US"


def test_mask_key() -> None:
    assert mask_key("dk_abcdefghijklmnop") == "dk_a...mnop"
    assert mask_key("short") == "****"
    assert mask_key("12345678") == "****"
    assert mask_key("123456789") == "1234...6789"
