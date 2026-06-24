"""Tests for domain_input.py and plan_gate.py — two critical untested paths.

domain_input: handles three distinct input modes (file, stdin, inline) and
enforces a 10,000-domain cap. Bugs here silently pass wrong domains to the API.

plan_gate: guards paid-tier commands. A regression could expose Team/Enterprise
endpoints to Starter users, causing unexpected API charges or auth errors.
"""

from __future__ import annotations

import csv
import io
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import click
import pytest

from discolike.domain_input import (
    MAX_DOMAINS,
    read_domains,
    validate_domain_count,
)
from discolike.errors import PlanGateError, ValidationError


# ---------------------------------------------------------------------------
# domain_input tests
# ---------------------------------------------------------------------------


class TestReadDomainsFromFile:
    def test_plain_text_file(self, tmp_path: Path) -> None:
        f = tmp_path / "domains.txt"
        f.write_text("acme.com\nstripe.com\n\nzapier.com\n")
        result = read_domains(str(f), ())
        assert result == ["acme.com", "stripe.com", "zapier.com"]

    def test_csv_file_domain_header(self, tmp_path: Path) -> None:
        f = tmp_path / "leads.csv"
        with f.open("w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=["domain", "name"])
            writer.writeheader()
            writer.writerow({"domain": "hubspot.com", "name": "HubSpot"})
            writer.writerow({"domain": "salesforce.com", "name": "Salesforce"})
        result = read_domains(str(f), ())
        assert result == ["hubspot.com", "salesforce.com"]

    def test_csv_file_website_header(self, tmp_path: Path) -> None:
        """'website' column header should be recognized."""
        f = tmp_path / "leads.csv"
        with f.open("w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=["website", "company"])
            writer.writeheader()
            writer.writerow({"website": "notion.so", "company": "Notion"})
        result = read_domains(str(f), ())
        assert result == ["notion.so"]

    def test_csv_file_url_header(self, tmp_path: Path) -> None:
        """'url' column header should be recognized."""
        f = tmp_path / "leads.csv"
        with f.open("w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=["url", "title"])
            writer.writeheader()
            writer.writerow({"url": "linear.app", "title": "Linear"})
        result = read_domains(str(f), ())
        assert result == ["linear.app"]

    def test_csv_file_no_recognized_header_uses_first_column(
        self, tmp_path: Path
    ) -> None:
        """When no recognized header exists, the first column is used."""
        f = tmp_path / "leads.csv"
        with f.open("w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=["site", "employees"])
            writer.writeheader()
            writer.writerow({"site": "intercom.io", "employees": "500"})
        result = read_domains(str(f), ())
        assert result == ["intercom.io"]

    def test_text_file_strips_blank_lines(self, tmp_path: Path) -> None:
        f = tmp_path / "list.txt"
        f.write_text("\n\nacme.com\n\n\nstripe.com\n\n")
        result = read_domains(str(f), ())
        assert result == ["acme.com", "stripe.com"]


class TestReadDomainsInline:
    def test_inline_domains_returned_as_list(self) -> None:
        result = read_domains(None, ("acme.com", "stripe.com"))
        assert result == ["acme.com", "stripe.com"]

    def test_file_takes_priority_over_inline(self, tmp_path: Path) -> None:
        """If input_file is given, inline_domains are ignored."""
        f = tmp_path / "domains.txt"
        f.write_text("fromfile.com\n")
        result = read_domains(str(f), ("inline.com",))
        assert result == ["fromfile.com"]


class TestReadDomainsStdin:
    def test_stdin_plain_text(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake_stdin = io.StringIO("domain1.com\ndomain2.com\n")
        monkeypatch.setattr(sys, "stdin", fake_stdin)
        # isatty() returns False for StringIO, so no need to patch
        result = read_domains(None, ())
        assert result == ["domain1.com", "domain2.com"]

    def test_stdin_json_records(self, monkeypatch: pytest.MonkeyPatch) -> None:
        payload = json.dumps({"records": [{"domain": "a.com"}, {"domain": "b.com"}]})
        fake_stdin = io.StringIO(payload)
        monkeypatch.setattr(sys, "stdin", fake_stdin)
        result = read_domains(None, ())
        assert result == ["a.com", "b.com"]

    def test_stdin_json_array(self, monkeypatch: pytest.MonkeyPatch) -> None:
        payload = json.dumps([{"domain": "x.com"}, {"domain": "y.com"}])
        fake_stdin = io.StringIO(payload)
        monkeypatch.setattr(sys, "stdin", fake_stdin)
        result = read_domains(None, ())
        assert result == ["x.com", "y.com"]

    def test_stdin_empty_raises_usage_error_when_tty(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When stdin is a TTY and no other input, raise click.UsageError."""
        fake_tty = MagicMock()
        fake_tty.isatty.return_value = True
        monkeypatch.setattr(sys, "stdin", fake_tty)
        with pytest.raises(click.UsageError):
            read_domains(None, ())


class TestValidateDomainCount:
    def test_within_limit_passes(self) -> None:
        domains = ["d.com"] * MAX_DOMAINS
        # Should not raise
        validate_domain_count(domains)

    def test_over_limit_raises(self) -> None:
        domains = ["d.com"] * (MAX_DOMAINS + 1)
        with pytest.raises(ValidationError, match="Too many domains"):
            validate_domain_count(domains)

    def test_error_message_includes_count(self) -> None:
        domains = ["d.com"] * 15_000
        with pytest.raises(ValidationError, match="15,000"):
            validate_domain_count(domains)


# ---------------------------------------------------------------------------
# plan_gate tests
# ---------------------------------------------------------------------------


class TestRequirePlan:
    """Tests for the @require_plan decorator.

    plan_gate.py imports _get_context from discolike.cli at call time (inside
    the wrapper), so the correct patch target is 'discolike.cli._get_context',
    not 'discolike.commands.plan_gate._get_context'.
    """

    def _make_cli_ctx(self, plan: str) -> MagicMock:
        """Create a minimal CliContext mock with a given plan."""
        from discolike.cost import CostTracker

        cli_ctx = MagicMock()
        cli_ctx.cost_tracker = CostTracker(plan=plan)
        return cli_ctx

    def test_team_plan_allows_contacts(self) -> None:
        """Team plan should pass the gate for 'contacts' (requires team)."""
        from discolike.commands.plan_gate import require_plan

        called = []

        @require_plan("contacts")
        def fake_command() -> None:
            called.append(True)

        cli_ctx = self._make_cli_ctx("team")

        with patch("discolike.cli._get_context", return_value=cli_ctx):
            with patch("click.get_current_context") as mock_ctx:
                mock_ctx.return_value = MagicMock()
                fake_command()

        assert called == [True]

    def test_starter_plan_blocked_from_contacts(self) -> None:
        """Starter plan should be blocked from 'contacts' (requires team)."""
        from discolike.commands.plan_gate import require_plan

        @require_plan("contacts")
        def fake_command() -> None:
            pass  # pragma: no cover — should not reach here

        cli_ctx = self._make_cli_ctx("starter")

        with patch("discolike.cli._get_context", return_value=cli_ctx):
            with patch("click.get_current_context") as mock_ctx:
                mock_ctx.return_value = MagicMock()
                with pytest.raises(PlanGateError) as exc_info:
                    fake_command()

        error = exc_info.value
        assert "contacts" in str(error)
        assert "team" in str(error).lower()
        assert error.exit_code == 4

    def test_pro_plan_blocked_from_subsidiaries(self) -> None:
        """subsidiaries requires enterprise; pro should be blocked."""
        from discolike.commands.plan_gate import require_plan

        @require_plan("subsidiaries")
        def fake_command() -> None:
            pass  # pragma: no cover

        cli_ctx = self._make_cli_ctx("pro")

        with patch("discolike.cli._get_context", return_value=cli_ctx):
            with patch("click.get_current_context") as mock_ctx:
                mock_ctx.return_value = MagicMock()
                with pytest.raises(PlanGateError) as exc_info:
                    fake_command()

        assert "enterprise" in str(exc_info.value).lower()

    def test_enterprise_plan_allows_subsidiaries(self) -> None:
        """Enterprise plan should be allowed to run subsidiaries."""
        from discolike.commands.plan_gate import require_plan

        called = []

        @require_plan("subsidiaries")
        def fake_command() -> None:
            called.append(True)

        cli_ctx = self._make_cli_ctx("enterprise")

        with patch("discolike.cli._get_context", return_value=cli_ctx):
            with patch("click.get_current_context") as mock_ctx:
                mock_ctx.return_value = MagicMock()
                fake_command()

        assert called == [True]

    def test_unknown_plan_treated_as_starter(self) -> None:
        """An unrecognized plan string should default to level 0 (starter)."""
        from discolike.commands.plan_gate import require_plan

        @require_plan("contacts")
        def fake_command() -> None:
            pass  # pragma: no cover

        cli_ctx = self._make_cli_ctx("mystery_plan")

        with patch("discolike.cli._get_context", return_value=cli_ctx):
            with patch("click.get_current_context") as mock_ctx:
                mock_ctx.return_value = MagicMock()
                with pytest.raises(PlanGateError):
                    fake_command()

    def test_require_plan_invalid_command_raises_value_error(self) -> None:
        """Decorating with an unregistered command name is a programming error."""
        from discolike.commands.plan_gate import require_plan

        with pytest.raises(ValueError, match="No plan gate defined"):
            require_plan("nonexistent_command")
