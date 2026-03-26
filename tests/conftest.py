"""Shared test fixtures for DiscoLike CLI tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict | list:
    """Load a JSON fixture file."""
    with open(FIXTURES / name) as f:
        return json.load(f)


def make_cli_runner() -> CliRunner:
    """Create a CliRunner with separate stderr capture."""
    return CliRunner(mix_stderr=False)


@pytest.fixture(autouse=True)
def mock_config_dir(tmp_path, monkeypatch):
    """Redirect config dir to tmp_path for all tests so no real ~/.discolike is touched."""
    monkeypatch.setattr("discolike.config.get_config_dir", lambda: tmp_path)
    monkeypatch.setattr("discolike.cache.get_config_dir", lambda: tmp_path)
    monkeypatch.setenv("DISCOLIKE_API_KEY", "dk_test_key")
