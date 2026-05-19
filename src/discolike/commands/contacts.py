"""Contacts commands (Team+ plan required)."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import click

from discolike.cli import _get_context, get_client
from discolike.commands.plan_gate import require_plan
from discolike.domain_input import validate_domain_count
from discolike.errors import ValidationError, handle_errors


@click.group("contacts", invoke_without_command=True)
@click.option("--domain", required=False, help="Company domain to search")
@click.option("--title", type=str, default=None, help="Job title filter")
@click.option("--max-records", type=int, default=25, help="Max contacts to return")
@click.option("--output", "-o", type=click.Path(), default=None, help="Save to file")
@handle_errors
@require_plan("contacts")
@click.pass_context
def contacts(
    ctx: click.Context,
    domain: str | None,
    title: str | None,
    max_records: int,
    output: str | None,
) -> None:
    """Search for B2B contacts at a company.

    Subcommands:
      discolike contacts match --name NAME        Find contact by person's name
      discolike contacts bulk-match --input FILE   Batch-resolve contact names
    """
    # invoke_without_command=True: if no subcommand, run search
    if ctx.invoked_subcommand is not None:
        return

    if not domain:
        raise click.UsageError("--domain is required for contact search.")

    client = get_client(ctx)
    cli_ctx = _get_context(ctx)
    result = client.contacts(domain, title=title, max_records=max_records)

    if output:
        from discolike.exporters.json_export import export_json

        export_json(result, output)
        cli_ctx.output.success(f"Saved to {output}")
    else:
        cli_ctx.output.render(
            result,
            title=f"Contacts: {domain}",
            cost=client.cost_tracker.last_call,
        )


@contacts.command("match")
@click.option("--name", required=True, help="Person's full name")
@click.option("--company", default=None, help="Company name (optional, improves accuracy)")
@handle_errors
@require_plan("contact_match")
@click.pass_context
def contacts_match(
    ctx: click.Context,
    name: str,
    company: str | None,
) -> None:
    """Find contact details for a person (reverse lookup).

    Given a person's name, returns their contact information
    including domain, email, and title where available.
    """
    client = get_client(ctx)
    cli_ctx = _get_context(ctx)
    result = client.contact_match(name, company=company)

    cli_ctx.output.render(
        result,
        title=f"Contact Match: {name}",
        cost=client.cost_tracker.last_call,
    )


@contacts.command("bulk-match")
@click.option(
    "--input", "input_file",
    type=click.Path(exists=True),
    default=None,
    help="CSV file with name,company columns",
)
@click.option(
    "--name", "-n", "name_entries",
    multiple=True,
    help='Contact name and optional company: "Jane Doe" or "Jane Doe, Acme Corp"',
)
@click.option(
    "--yes",
    "auto_confirm",
    is_flag=True,
    default=False,
    help="Skip confirmation prompt",
)
@handle_errors
@require_plan("contact_bulk_match")
@click.pass_context
def contacts_bulk_match(
    ctx: click.Context,
    input_file: str | None,
    name_entries: tuple[str, ...],
    auto_confirm: bool,
) -> None:
    """Batch-resolve contact names to profiles.

    Provide names via --input CSV (name, company columns), --name flags,
    or pipe JSON via stdin. Each entry needs at minimum a name; company
    is optional but improves accuracy.

    \b
    Examples:
      discolike contacts bulk-match --name "Jane Doe"
      discolike contacts bulk-match --name "Jane Doe, Acme Corp"
      discolike contacts bulk-match --input names.csv
    """
    client = get_client(ctx)
    cli_ctx = _get_context(ctx)

    contacts_list = _parse_contact_names(input_file, name_entries)
    validate_domain_count(contacts_list)

    if not contacts_list:
        raise click.UsageError(
            "No names provided. Use --input, --name, or pipe via stdin."
        )

    if len(contacts_list) > 100 and not auto_confirm and sys.stdin.isatty():
        click.confirm(
            f"Match {len(contacts_list)} contacts?",
            default=False,
            abort=True,
        )

    cli_ctx.output.status(f"Matching {len(contacts_list)} contacts...")
    result = client.contact_bulk_match(contacts_list)

    cli_ctx.output.render(
        result,
        title=f"Bulk Contact Match ({len(contacts_list)} names)",
        cost=client.cost_tracker.last_call,
    )


def _parse_contact_names(
    input_file: str | None,
    name_entries: tuple[str, ...],
) -> list[dict[str, str]]:
    """Parse contact names from file, inline args, or stdin.

    Returns list of {"name": str, "company": str (optional)} dicts.
    """
    if input_file is not None:
        path = Path(input_file)
        if path.suffix.lower() == ".csv":
            return _parse_contacts_csv(path)
        return _parse_contacts_text(path)

    if name_entries:
        contacts: list[dict[str, str]] = []
        for entry in name_entries:
            parts = [p.strip() for p in entry.split(",", 1)]
            contact: dict[str, str] = {"name": parts[0]}
            if len(parts) > 1 and parts[1]:
                contact["company"] = parts[1]
            contacts.append(contact)
        return contacts

    if not sys.stdin.isatty():
        import json

        content = sys.stdin.read().strip()
        if content.startswith("[") or content.startswith("{"):
            parsed = json.loads(content)
            if isinstance(parsed, dict) and "contacts" in parsed:
                return parsed["contacts"]
            if isinstance(parsed, list):
                return parsed
        # Plain text: one name per line, optional company after comma
        return [
            _parse_single_name(line)
            for line in content.splitlines()
            if line.strip()
        ]

    return []


def _parse_single_name(line: str) -> dict[str, str]:
    """Parse a single line into {name, company?}."""
    parts = [p.strip() for p in line.split(",", 1)]
    contact: dict[str, str] = {"name": parts[0]}
    if len(parts) > 1 and parts[1]:
        contact["company"] = parts[1]
    return contact


def _parse_contacts_csv(path: Path) -> list[dict[str, str]]:
    """Parse a CSV with optional name, company columns."""
    results: list[dict[str, str]] = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            return results
        lowered = {h.lower(): h for h in reader.fieldnames}
        name_col = lowered.get("name")
        company_col = lowered.get("company")
        if name_col is None:
            raise ValidationError(
                "CSV must have a 'name' column.",
                suggestion="Expected columns: name, company (optional)",
            )
        for row in reader:
            contact: dict[str, str] = {"name": row[name_col].strip()}
            if company_col and row.get(company_col, "").strip():
                contact["company"] = row[company_col].strip()
            results.append(contact)
    return results


def _parse_contacts_text(path: Path) -> list[dict[str, str]]:
    """Parse a plain text file — one name per line."""
    content = path.read_text(encoding="utf-8")
    return [
        _parse_single_name(line)
        for line in content.splitlines()
        if line.strip()
    ]
