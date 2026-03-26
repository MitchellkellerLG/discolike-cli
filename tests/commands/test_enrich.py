"""Tests for enrichment commands: profile, score, growth."""

from __future__ import annotations

import json

import httpx
import respx
from click.testing import CliRunner

from discolike.cli import cli
from tests.conftest import load_fixture

BASE_URL = "https://api.discolike.com/v1"


class TestProfile:
    @respx.mock
    def test_profile_table_output(self) -> None:
        fixture = load_fixture("business_profile.json")
        respx.get(f"{BASE_URL}/bizdata").mock(
            return_value=httpx.Response(200, json=fixture)
        )
        runner = CliRunner()
        result = runner.invoke(cli, ["profile", "example-agency.com"])
        assert result.exit_code == 0
        assert "example-agency.com" in result.output

    @respx.mock
    def test_profile_json_output(self) -> None:
        fixture = load_fixture("business_profile.json")
        respx.get(f"{BASE_URL}/bizdata").mock(
            return_value=httpx.Response(200, json=fixture)
        )
        runner = CliRunner()
        result = runner.invoke(cli, ["--json", "profile", "example-agency.com"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["domain"] == "example-agency.com"
        assert data["score"] == 450
        assert data["name"] == "Example Agency"

    @respx.mock
    def test_profile_with_fields(self) -> None:
        fixture = load_fixture("business_profile.json")
        route = respx.get(f"{BASE_URL}/bizdata").mock(
            return_value=httpx.Response(200, json=fixture)
        )
        runner = CliRunner()
        result = runner.invoke(
            cli, ["--json", "profile", "example-agency.com", "--fields", "domain,name,score"]
        )
        assert result.exit_code == 0
        # Verify the API was called
        assert route.call_count == 1

    @respx.mock
    def test_profile_save_to_file(self, tmp_path) -> None:
        fixture = load_fixture("business_profile.json")
        respx.get(f"{BASE_URL}/bizdata").mock(
            return_value=httpx.Response(200, json=fixture)
        )
        output_file = tmp_path / "profile.json"
        runner = CliRunner()
        result = runner.invoke(
            cli, ["profile", "example-agency.com", "-o", str(output_file)]
        )
        assert result.exit_code == 0
        assert output_file.exists()
        data = json.loads(output_file.read_text())
        assert data["domain"] == "example-agency.com"


class TestScore:
    @respx.mock
    def test_score_table_output(self) -> None:
        fixture = load_fixture("score_result.json")
        respx.get(f"{BASE_URL}/score").mock(
            return_value=httpx.Response(200, json=fixture)
        )
        runner = CliRunner()
        result = runner.invoke(cli, ["score", "example-agency.com"])
        assert result.exit_code == 0
        assert "example-agency.com" in result.output

    @respx.mock
    def test_score_json_output(self) -> None:
        fixture = load_fixture("score_result.json")
        respx.get(f"{BASE_URL}/score").mock(
            return_value=httpx.Response(200, json=fixture)
        )
        runner = CliRunner()
        result = runner.invoke(cli, ["--json", "score", "example-agency.com"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["domain"] == "example-agency.com"
        assert data["score"] == 450
        assert data["parameters"]["base_score"] == 400


class TestGrowth:
    @respx.mock
    def test_growth_table_output(self) -> None:
        fixture = load_fixture("growth_result.json")
        respx.get(f"{BASE_URL}/growth").mock(
            return_value=httpx.Response(200, json=fixture)
        )
        runner = CliRunner()
        result = runner.invoke(cli, ["growth", "example-agency.com"])
        assert result.exit_code == 0
        assert "example-agency.com" in result.output

    @respx.mock
    def test_growth_json_output(self) -> None:
        fixture = load_fixture("growth_result.json")
        respx.get(f"{BASE_URL}/growth").mock(
            return_value=httpx.Response(200, json=fixture)
        )
        runner = CliRunner()
        result = runner.invoke(cli, ["--json", "growth", "example-agency.com"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["domain"] == "example-agency.com"
        assert data["score_growth_3m"] == 0.12
