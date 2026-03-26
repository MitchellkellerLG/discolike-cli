"""Bulk firmographic data append command."""

from __future__ import annotations

import click

from discolike.cli import _get_context, get_client
from discolike.errors import ValidationError, handle_errors


@click.command("append")
@click.option(
    "--input",
    "input_file",
    required=True,
    type=click.Path(exists=True),
    help="Input file with domains",
)
@click.option(
    "--fields",
    "field_list",
    required=True,
    type=str,
    help="Comma-separated fields to append",
)
@click.option("--output", "-o", required=True, type=click.Path(), help="Output file path")
@handle_errors
@click.pass_context
def append(
    ctx: click.Context,
    input_file: str,
    field_list: str,
    output: str,
) -> None:
    """Bulk-append firmographic data to a domain list."""
    from pathlib import Path

    client = get_client(ctx)
    cli_ctx = _get_context(ctx)
    fields = [f.strip() for f in field_list.split(",")]

    # Read domains from file
    domains: list[str] = []
    with open(input_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                domains.append(line.split(",")[0].strip())

    if not domains:
        raise ValidationError("No domains found in input file.")

    cli_ctx.output.status(f"Enriching {len(domains)} domains...")

    results = client.append(domains, fields)
    records = [r.model_dump(mode="json") for r in results]

    output_path = Path(output)
    if output_path.suffix.lower() == ".csv":
        from discolike.exporters.csv_export import export_csv

        export_csv(records, output_path, columns=fields)
    else:
        from discolike.exporters.json_export import export_json

        export_json({"records": records, "count": len(records)}, output_path)

    cli_ctx.output.success(f"Enriched {len(records)} domains -> {output}")
