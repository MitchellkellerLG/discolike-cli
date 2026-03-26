"""Tests for saved queries commands."""

from __future__ import annotations

import json

import httpx
import respx
from click.testing import CliRunner

from discolike.cli import cli
from tests.conftest import load_fixture

BASE_URL = "https://api.discolike.com/v1"


class TestSavedList:
    @respx.mock
    def test_saved_list_json(self) -> None:
        fixture = load_fixture("saved_queries.json")
        respx.get(f"{BASE_URL}/queries/saved").mock(
            return_value=httpx.Response(200, json=fixture)
        )
        runner = CliRunner()
        result = runner.invoke(cli, ["--json", "saved", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["count"] == 1
        assert data["records"][0]["query_id"] == "q_abc123"

    @respx.mock
    def test_saved_list_table(self) -> None:
        fixture = load_fixture("saved_queries.json")
        respx.get(f"{BASE_URL}/queries/saved").mock(
            return_value=httpx.Response(200, json=fixture)
        )
        runner = CliRunner()
        result = runner.invoke(cli, ["saved", "list"])
        assert result.exit_code == 0
        assert "q_abc123" in result.output


class TestSavedSave:
    @respx.mock
    def test_save_with_domains_flag(self) -> None:
        fixture = load_fixture("save_exclusion.json")
        respx.post(f"{BASE_URL}/queries/exclusion-list").mock(
            return_value=httpx.Response(200, json=fixture)
        )
        runner = CliRunner()
        result = runner.invoke(
            cli, ["saved", "save", "--name", "Test List", "--domains", "a.com,b.com"]
        )
        assert result.exit_code == 0

    @respx.mock
    def test_save_with_input_file(self, tmp_path) -> None:
        fixture = load_fixture("save_exclusion.json")
        respx.post(f"{BASE_URL}/queries/exclusion-list").mock(
            return_value=httpx.Response(200, json=fixture)
        )
        # Create a domain file
        domain_file = tmp_path / "domains.txt"
        domain_file.write_text("skip1.com\nskip2.com\n# comment\n")

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["saved", "save", "--name", "File List", "--input", str(domain_file)],
        )
        assert result.exit_code == 0

    def test_save_no_domains_or_file_errors(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["saved", "save", "--name", "Empty"])
        # Should fail with ValidationError (exit code 6)
        assert result.exit_code == 6

    @respx.mock
    def test_save_with_csv_input(self, tmp_path) -> None:
        fixture = load_fixture("save_exclusion.json")
        respx.post(f"{BASE_URL}/queries/exclusion-list").mock(
            return_value=httpx.Response(200, json=fixture)
        )
        csv_file = tmp_path / "domains.csv"
        csv_file.write_text("domain1.com,Company A\ndomain2.com,Company B\n")

        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["saved", "save", "--name", "CSV List", "--input", str(csv_file)],
        )
        assert result.exit_code == 0
