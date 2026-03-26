"""Tests for costs command."""

from __future__ import annotations

from click.testing import CliRunner

from discolike.cli import cli


class TestCostsCommand:
    def test_costs_no_entries(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["costs"])
        assert result.exit_code == 0
        assert "No costs recorded" in result.output

    def test_costs_no_cache_mode(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--no-cache", "costs"])
        assert result.exit_code == 0
        assert "No cache available" in result.output

    def test_costs_reset(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["costs", "--reset"])
        assert result.exit_code == 0
        assert "Reset" in result.output
