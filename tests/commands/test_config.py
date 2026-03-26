"""Tests for config commands."""

from __future__ import annotations

from click.testing import CliRunner

from discolike.cli import cli


class TestConfigShow:
    def test_config_show_with_env_key(self, monkeypatch) -> None:
        monkeypatch.setenv("DISCOLIKE_API_KEY", "dk_test_1234567890")
        runner = CliRunner()
        result = runner.invoke(cli, ["config", "show"])
        assert result.exit_code == 0
        assert "dk_t...7890" in result.output
        assert "(from env)" in result.output

    def test_config_show_no_key(self, monkeypatch) -> None:
        monkeypatch.delenv("DISCOLIKE_API_KEY", raising=False)
        runner = CliRunner()
        result = runner.invoke(cli, ["config", "show"])
        assert result.exit_code == 0
        assert "not set" in result.output

    def test_config_show_from_config_file(self, tmp_path, monkeypatch) -> None:
        monkeypatch.delenv("DISCOLIKE_API_KEY", raising=False)
        # Write a config file
        config_file = tmp_path / "config.yaml"
        config_file.write_text("api_key: dk_from_config_file\n")
        runner = CliRunner()
        result = runner.invoke(cli, ["config", "show"])
        assert result.exit_code == 0
        assert "(from config)" in result.output


class TestConfigSet:
    def test_config_set_api_key(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["config", "set", "api_key", "dk_newkey12345678"])
        assert result.exit_code == 0
        assert "dk_n...5678" in result.output  # masked

    def test_config_set_non_key(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["config", "set", "default_country", "US"])
        assert result.exit_code == 0
        assert "US" in result.output


class TestConfigClear:
    def test_config_clear_specific_key(self) -> None:
        runner = CliRunner()
        # Set then clear
        runner.invoke(cli, ["config", "set", "default_country", "US"])
        result = runner.invoke(cli, ["config", "clear", "default_country"])
        assert result.exit_code == 0
        assert "Cleared default_country" in result.output

    def test_config_clear_missing_key(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["config", "clear", "nonexistent"])
        assert result.exit_code == 0
        assert "not found" in result.output

    def test_config_clear_all(self) -> None:
        runner = CliRunner()
        runner.invoke(cli, ["config", "set", "default_country", "US"])
        result = runner.invoke(cli, ["config", "clear"])
        assert result.exit_code == 0
        assert "Cleared all configuration" in result.output
