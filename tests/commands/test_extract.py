"""Tests for extract command."""

from __future__ import annotations

import json

import httpx
import respx
from click.testing import CliRunner

from discolike.cli import cli
from tests.conftest import load_fixture

BASE_URL = "https://api.discolike.com/v1"


class TestExtract:
    @respx.mock
    def test_extract_table_output(self) -> None:
        fixture = load_fixture("extract_result.json")
        respx.get(f"{BASE_URL}/extract").mock(
            return_value=httpx.Response(200, json=fixture)
        )
        runner = CliRunner()
        result = runner.invoke(cli, ["extract", "example-agency.com"])
        assert result.exit_code == 0
        assert "example-agency.com" in result.output

    @respx.mock
    def test_extract_json_output(self) -> None:
        fixture = load_fixture("extract_result.json")
        respx.get(f"{BASE_URL}/extract").mock(
            return_value=httpx.Response(200, json=fixture)
        )
        runner = CliRunner()
        result = runner.invoke(cli, ["--json", "extract", "example-agency.com"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["domain"] == "example-agency.com"
        assert "B2B lead generation" in data["text"]

    @respx.mock
    def test_extract_dry_run(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--dry-run", "--json", "extract", "test.com"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["domain"] == "test.com"
        # In dry run, text should be None
        assert data.get("text") is None
