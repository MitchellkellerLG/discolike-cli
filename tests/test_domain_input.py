"""Tests for domain_input.py -- file/stdin/inline/CSV/JSON input modes."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from discolike.errors import ValidationError


class TestReadDomainsFromTextFile:
    """Tests for reading domains from plain text files."""

    def test_reads_newline_separated_text_file(self, tmp_path: Path) -> None:
        """read_domains reads a plain text file with one domain per line."""
        domain_file = tmp_path / "domains.txt"
        domain_file.write_text("acme.com\nstripe.com\nnotify.io\n")

        from discolike.domain_input import read_domains

        result = read_domains(input_file=str(domain_file), inline_domains=())
        assert result == ["acme.com", "stripe.com", "notify.io"]

    def test_strips_blank_lines_from_text_file(self, tmp_path: Path) -> None:
        """read_domains strips empty lines from text file input."""
        domain_file = tmp_path / "domains.txt"
        domain_file.write_text("acme.com\n\nstripe.com\n\n")

        from discolike.domain_input import read_domains

        result = read_domains(input_file=str(domain_file), inline_domains=())
        assert result == ["acme.com", "stripe.com"]

    def test_strips_whitespace_from_domains_in_text_file(self, tmp_path: Path) -> None:
        """read_domains strips leading/trailing whitespace from each domain."""
        domain_file = tmp_path / "domains.txt"
        domain_file.write_text("  acme.com  \n  stripe.com\n")

        from discolike.domain_input import read_domains

        result = read_domains(input_file=str(domain_file), inline_domains=())
        assert result == ["acme.com", "stripe.com"]


class TestReadDomainsFromCSV:
    """Tests for reading domains from CSV files."""

    def test_reads_csv_with_domain_header(self, tmp_path: Path) -> None:
        """read_domains detects 'domain' column header in CSV."""
        csv_file = tmp_path / "domains.csv"
        csv_file.write_text("domain,name\nacme.com,Acme\nstripe.com,Stripe\n")

        from discolike.domain_input import read_domains

        result = read_domains(input_file=str(csv_file), inline_domains=())
        assert result == ["acme.com", "stripe.com"]

    def test_reads_csv_with_website_header(self, tmp_path: Path) -> None:
        """read_domains detects 'website' column header in CSV."""
        csv_file = tmp_path / "leads.csv"
        csv_file.write_text("website,company\nacme.com,Acme Inc\nstripe.com,Stripe Inc\n")

        from discolike.domain_input import read_domains

        result = read_domains(input_file=str(csv_file), inline_domains=())
        assert result == ["acme.com", "stripe.com"]

    def test_reads_csv_with_url_header(self, tmp_path: Path) -> None:
        """read_domains detects 'url' column header in CSV."""
        csv_file = tmp_path / "leads.csv"
        csv_file.write_text("url,company\nacme.com,Acme\n")

        from discolike.domain_input import read_domains

        result = read_domains(input_file=str(csv_file), inline_domains=())
        assert result == ["acme.com"]

    def test_csv_fallback_to_first_column(self, tmp_path: Path) -> None:
        """read_domains falls back to first column when no recognized header."""
        csv_file = tmp_path / "data.csv"
        csv_file.write_text("company_url,revenue\nacme.com,1M\nstripe.com,2M\n")

        from discolike.domain_input import read_domains

        result = read_domains(input_file=str(csv_file), inline_domains=())
        assert result == ["acme.com", "stripe.com"]

    def test_csv_header_matching_is_case_insensitive(self, tmp_path: Path) -> None:
        """CSV header matching is case-insensitive (Domain, DOMAIN, domain all match)."""
        csv_file = tmp_path / "leads.csv"
        csv_file.write_text("Domain,Name\nacme.com,Acme\n")

        from discolike.domain_input import read_domains

        result = read_domains(input_file=str(csv_file), inline_domains=())
        assert result == ["acme.com"]


class TestReadDomainsInline:
    """Tests for inline domain input via --domain flag."""

    def test_returns_inline_domains_as_list(self) -> None:
        """read_domains returns inline_domains tuple as a list."""
        from discolike.domain_input import read_domains

        result = read_domains(input_file=None, inline_domains=("acme.com", "stripe.com"))
        assert result == ["acme.com", "stripe.com"]

    def test_single_inline_domain(self) -> None:
        """read_domains handles a single inline domain."""
        from discolike.domain_input import read_domains

        result = read_domains(input_file=None, inline_domains=("acme.com",))
        assert result == ["acme.com"]


class TestReadDomainsFromStdin:
    """Tests for reading domains from stdin pipe."""

    def test_raises_usage_error_when_stdin_is_tty(self) -> None:
        """read_domains raises UsageError when stdin is TTY and no input/inline provided."""
        import click

        from discolike.domain_input import read_domains

        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True
            with pytest.raises(click.UsageError, match="--input FILE"):
                read_domains(input_file=None, inline_domains=())

    def test_reads_plain_text_from_stdin_pipe(self) -> None:
        """read_domains reads newline-separated domains from non-TTY stdin."""
        from discolike.domain_input import read_domains

        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = False
            mock_stdin.read.return_value = "acme.com\nstripe.com\n"

            result = read_domains(input_file=None, inline_domains=())
            assert result == ["acme.com", "stripe.com"]

    def test_reads_json_discover_output_from_stdin(self) -> None:
        """read_domains parses JSON with records[].domain from stdin."""
        from discolike.domain_input import read_domains

        json_input = json.dumps({
            "records": [
                {"domain": "acme.com", "name": "Acme"},
                {"domain": "stripe.com", "name": "Stripe"},
            ]
        })

        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = False
            mock_stdin.read.return_value = json_input

            result = read_domains(input_file=None, inline_domains=())
            assert result == ["acme.com", "stripe.com"]

    def test_reads_json_list_with_domain_field_from_stdin(self) -> None:
        """read_domains parses JSON array with domain fields from stdin."""
        from discolike.domain_input import read_domains

        json_input = json.dumps([
            {"domain": "acme.com"},
            {"domain": "stripe.com"},
        ])

        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = False
            mock_stdin.read.return_value = json_input

            result = read_domains(input_file=None, inline_domains=())
            assert result == ["acme.com", "stripe.com"]


class TestValidateDomainCount:
    """Tests for validate_domain_count cap enforcement."""

    def test_raises_validation_error_above_10k(self) -> None:
        """validate_domain_count raises ValidationError for > 10,000 domains."""
        from discolike.domain_input import validate_domain_count

        with pytest.raises(ValidationError, match="10,000"):
            validate_domain_count(["x.com"] * 10_001)

    def test_does_not_raise_at_exactly_10k(self) -> None:
        """validate_domain_count does not raise for exactly 10,000 domains."""
        from discolike.domain_input import validate_domain_count

        validate_domain_count(["x.com"] * 10_000)  # Should not raise

    def test_does_not_raise_for_small_list(self) -> None:
        """validate_domain_count does not raise for small domain lists."""
        from discolike.domain_input import validate_domain_count

        validate_domain_count(["acme.com", "stripe.com"])  # Should not raise


class TestConstants:
    """Tests for module-level constants."""

    def test_max_domains_constant(self) -> None:
        """MAX_DOMAINS is 10,000."""
        from discolike.domain_input import MAX_DOMAINS

        assert MAX_DOMAINS == 10_000


class TestValidateResultModel:
    """Tests for ValidateResult Pydantic model in types.py."""

    def test_validate_result_accepts_full_payload(self) -> None:
        """ValidateResult model accepts all expected fields."""
        from discolike.types import ValidateResult

        result = ValidateResult(
            domain="acme.com",
            Fit="yes",
            Confidence="high",
            Reasoning="Matches ICP perfectly",
        )
        assert result.domain == "acme.com"
        assert result.Fit == "yes"
        assert result.Confidence == "high"
        assert result.Reasoning == "Matches ICP perfectly"

    def test_validate_result_reasoning_defaults_to_empty_string(self) -> None:
        """ValidateResult.Reasoning has a default empty string."""
        from discolike.types import ValidateResult

        result = ValidateResult(domain="acme.com", Fit="no", Confidence="low")
        assert result.Reasoning == ""
