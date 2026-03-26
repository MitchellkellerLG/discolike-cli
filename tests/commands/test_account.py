"""Tests for account commands."""

from __future__ import annotations

import json

import httpx
import respx
from click.testing import CliRunner

from discolike.cli import cli
from tests.conftest import load_fixture

BASE_URL = "https://api.discolike.com/v1"


class TestAccountStatus:
    @respx.mock
    def test_account_status_table_output(self) -> None:
        fixture = load_fixture("account_status.json")
        respx.get(f"{BASE_URL}/usage").mock(
            return_value=httpx.Response(200, json=fixture)
        )
        runner = CliRunner()
        result = runner.invoke(cli, ["account", "status"])
        assert result.exit_code == 0
        assert "active" in result.output

    @respx.mock
    def test_account_status_json_output(self) -> None:
        fixture = load_fixture("account_status.json")
        respx.get(f"{BASE_URL}/usage").mock(
            return_value=httpx.Response(200, json=fixture)
        )
        runner = CliRunner()
        result = runner.invoke(cli, ["--json", "account", "status"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["account_status"] == "active"
        assert data["plan"] == "starter"

    @respx.mock
    def test_account_status_auth_error(self, monkeypatch) -> None:
        monkeypatch.delenv("DISCOLIKE_API_KEY", raising=False)
        runner = CliRunner()
        result = runner.invoke(cli, ["account", "status"])
        # Should fail with exit code 2 (AuthError)
        assert result.exit_code == 2


class TestAccountUsage:
    @respx.mock
    def test_account_usage_json_output(self) -> None:
        fixture = load_fixture("account_status.json")
        respx.get(f"{BASE_URL}/usage").mock(
            return_value=httpx.Response(200, json=fixture)
        )
        runner = CliRunner()
        result = runner.invoke(cli, ["--json", "account", "usage"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["month_to_date_requests"] == 42
