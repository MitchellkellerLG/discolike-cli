"""Shared domain list input parsing for CLI commands.

Handles three input modes:
  1. File input (--input): CSV with domain column sniffing, or plain text
  2. Stdin pipe: JSON (records[].domain or list of {domain}) or newline-separated text
  3. Inline (--domain): directly passed domain arguments

Domain cap: 10,000 domains max across all input modes.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import click

from discolike.errors import ValidationError

MAX_DOMAINS = 10_000

# CSV column headers that indicate a domain field (checked case-insensitively)
_DOMAIN_HEADERS = {"domain", "website", "url"}


def read_domains(
    input_file: str | None,
    inline_domains: tuple[str, ...],
) -> list[str]:
    """Parse domain list from file, stdin pipe, or inline args.

    Priority order:
    1. input_file (if provided)
    2. inline_domains (if non-empty)
    3. stdin (if not a TTY)

    Args:
        input_file: Path to CSV or text file with domains.
        inline_domains: Tuple of domains passed via --domain flag.

    Returns:
        List of domain strings (stripped, no empty values).

    Raises:
        click.UsageError: If stdin is a TTY and no input_file or inline_domains provided.
        ValidationError: If more than MAX_DOMAINS are read.
    """
    if input_file is not None:
        path = Path(input_file)
        if path.suffix.lower() == ".csv":
            return _parse_csv(path)
        return _parse_text(path)

    if inline_domains:
        return list(inline_domains)

    if not sys.stdin.isatty():
        return _read_stdin()

    raise click.UsageError(
        "Provide --input FILE, pipe domains via stdin, or use --domain."
    )


def _parse_text(path: Path) -> list[str]:
    """Parse a plain text file — one domain per line."""
    content = path.read_text(encoding="utf-8")
    return [line.strip() for line in content.splitlines() if line.strip()]


def _parse_csv(path: Path) -> list[str]:
    """Parse a CSV file, sniffing for domain/website/url column header.

    Falls back to the first column if no recognized header is found.
    """
    domains: list[str] = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            return domains

        # Find domain column: check for recognized header (case-insensitive)
        lowered = {h.lower(): h for h in reader.fieldnames}
        domain_col: str | None = None
        for candidate in _DOMAIN_HEADERS:
            if candidate in lowered:
                domain_col = lowered[candidate]
                break

        # Fall back to first column
        if domain_col is None:
            domain_col = reader.fieldnames[0]

        for row in reader:
            val = row.get(domain_col, "").strip()
            if val:
                domains.append(val)

    return domains


def _read_stdin() -> list[str]:
    """Read domains from stdin pipe.

    Supports:
    - JSON object with 'records' key: {"records": [{"domain": "x.com"}, ...]}
    - JSON array with 'domain' field: [{"domain": "x.com"}, ...]
    - Plain newline-separated text: "acme.com\nstripe.com\n"
    """
    content = sys.stdin.read().strip()
    if not content:
        return []

    # Detect JSON input
    if content.startswith("{") or content.startswith("["):
        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict) and "records" in parsed:
                records = parsed["records"]
            elif isinstance(parsed, list):
                records = parsed
            else:
                records = []
            return [
                r["domain"].strip()
                for r in records
                if isinstance(r, dict) and r.get("domain", "").strip()
            ]
        except (json.JSONDecodeError, KeyError):
            pass

    # Fall back to plain text
    return [line.strip() for line in content.splitlines() if line.strip()]


def validate_domain_count(domains: list[str]) -> None:
    """Raise ValidationError if domain list exceeds MAX_DOMAINS cap.

    Args:
        domains: List of domain strings to check.

    Raises:
        ValidationError: If len(domains) > MAX_DOMAINS.
    """
    if len(domains) > MAX_DOMAINS:
        raise ValidationError(
            f"Too many domains: {len(domains):,}. Maximum allowed is {MAX_DOMAINS:,}.",
            suggestion="Split your domain list into batches of 10,000 or fewer.",
        )
