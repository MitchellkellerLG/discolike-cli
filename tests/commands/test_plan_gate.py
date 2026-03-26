"""Tests for the plan gate decorator and plan-gated commands."""

from __future__ import annotations

import json

import httpx
import respx
from click.testing import CliRunner

from discolike.cli import cli

BASE_URL = "https://api.discolike.com/v1"


def _make_contacts_fixture() -> dict:
    """Minimal contacts response."""
    return {
        "records": [
            {"email": "john@example.com", "name": "John Doe", "title": "CEO"}
        ],
        "count": 1,
    }


def _make_match_fixture() -> dict:
    """Minimal match response."""
    return {"domain": "acme.com", "name": "Acme Corp", "confidence": 0.95}


def _make_vendors_fixture() -> dict:
    """Minimal vendors response."""
    return {
        "domain": "example-agency.com",
        "vendors": ["HubSpot", "Salesforce", "Slack"],
    }


def _make_subsidiaries_fixture() -> dict:
    """Minimal subsidiaries response."""
    return {
        "domain": "bigcorp.com",
        "subsidiaries": [
            {"domain": "sub1.bigcorp.com", "name": "Sub One"},
            {"domain": "sub2.bigcorp.com", "name": "Sub Two"},
        ],
    }


class TestPlanGateStarterDenied:
    """Starter plan should be denied from all plan-gated commands."""

    def test_contacts_denied_on_starter(self) -> None:
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(cli, ["contacts", "--domain", "test.com"])
        assert result.exit_code == 4
        assert "Team" in result.stderr
        assert "contacts" in result.stderr

    def test_match_denied_on_starter(self) -> None:
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(cli, ["match", "Acme Corp"])
        assert result.exit_code == 4
        assert "Team" in result.stderr
        assert "match" in result.stderr

    def test_vendors_denied_on_starter(self) -> None:
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(cli, ["vendors", "test.com"])
        assert result.exit_code == 4
        assert "Team" in result.stderr
        assert "vendors" in result.stderr

    def test_subsidiaries_denied_on_starter(self) -> None:
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(cli, ["subsidiaries", "test.com"])
        assert result.exit_code == 4
        assert "Enterprise" in result.stderr
        assert "subsidiaries" in result.stderr


class TestPlanGateTeamAllowed:
    """Team plan should allow contacts, match, vendors but deny subsidiaries."""

    @respx.mock
    def test_contacts_allowed_on_team(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "discolike.cost.CostTracker.plan",
            property(lambda self: "team"),
        )
        respx.get(f"{BASE_URL}/contacts").mock(
            return_value=httpx.Response(200, json=_make_contacts_fixture())
        )
        runner = CliRunner()
        result = runner.invoke(cli, ["--json", "contacts", "--domain", "test.com"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["count"] == 1

    @respx.mock
    def test_match_allowed_on_team(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "discolike.cost.CostTracker.plan",
            property(lambda self: "team"),
        )
        respx.get(f"{BASE_URL}/match").mock(
            return_value=httpx.Response(200, json=_make_match_fixture())
        )
        runner = CliRunner()
        result = runner.invoke(cli, ["--json", "match", "Acme Corp"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["domain"] == "acme.com"

    @respx.mock
    def test_vendors_allowed_on_team(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "discolike.cost.CostTracker.plan",
            property(lambda self: "team"),
        )
        respx.get(f"{BASE_URL}/vendors").mock(
            return_value=httpx.Response(200, json=_make_vendors_fixture())
        )
        runner = CliRunner()
        result = runner.invoke(cli, ["--json", "vendors", "example-agency.com"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "vendors" in data

    def test_subsidiaries_denied_on_team(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "discolike.cost.CostTracker.plan",
            property(lambda self: "team"),
        )
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(cli, ["subsidiaries", "test.com"])
        assert result.exit_code == 4
        assert "Enterprise" in result.stderr


class TestPlanGateEnterpriseAllowed:
    """Enterprise plan should allow everything."""

    @respx.mock
    def test_contacts_allowed_on_enterprise(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "discolike.cost.CostTracker.plan",
            property(lambda self: "enterprise"),
        )
        respx.get(f"{BASE_URL}/contacts").mock(
            return_value=httpx.Response(200, json=_make_contacts_fixture())
        )
        runner = CliRunner()
        result = runner.invoke(cli, ["--json", "contacts", "--domain", "test.com"])
        assert result.exit_code == 0

    @respx.mock
    def test_subsidiaries_allowed_on_enterprise(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "discolike.cost.CostTracker.plan",
            property(lambda self: "enterprise"),
        )
        respx.get(f"{BASE_URL}/subsidiaries").mock(
            return_value=httpx.Response(200, json=_make_subsidiaries_fixture())
        )
        runner = CliRunner()
        result = runner.invoke(cli, ["--json", "subsidiaries", "bigcorp.com"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "subsidiaries" in data


class TestPlanGateErrorMessage:
    """Plan gate should produce clear error messages."""

    def test_error_message_includes_command_and_plans(self) -> None:
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(cli, ["contacts", "--domain", "test.com"])
        assert result.exit_code == 4
        # Should mention the command
        assert "contacts" in result.stderr
        # Should mention required plan
        assert "Team" in result.stderr
        # Should mention current plan
        assert "Starter" in result.stderr

    def test_json_error_output(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--json", "contacts", "--domain", "test.com"])
        assert result.exit_code == 4
        data = json.loads(result.output)
        assert "error" in data
        assert "PLANGATEERROR" in data["code"]
        assert "suggestion" in data
