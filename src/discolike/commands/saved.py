"""Saved queries and exclusion list commands."""

from __future__ import annotations

import click

from discolike.cli import _get_context, get_client
from discolike.errors import handle_errors


@click.group("saved")
def saved() -> None:
    """Manage saved queries and exclusion lists."""


@saved.command("list")
@handle_errors
@click.pass_context
def saved_list(ctx: click.Context) -> None:
    """List all saved queries."""
    client = get_client(ctx)
    cli_ctx = _get_context(ctx)
    result = client.saved_queries()

    cli_ctx.output.render(
        result,
        title="Saved Queries",
        columns=["query_id", "query_name", "domain_count", "action", "mtime"],
        cost=client.cost_tracker.last_call,
    )


@saved.command("save")
@click.option("--name", required=True, help="Name for the exclusion list")
@click.option("--domains", type=str, default=None, help="Comma-separated domain list")
@click.option(
    "--input",
    "input_file",
    type=click.Path(exists=True),
    default=None,
    help="File with domains (one per line or CSV)",
)
@handle_errors
@click.pass_context
def saved_save(
    ctx: click.Context, name: str, domains: str | None, input_file: str | None
) -> None:
    """Save domains as an exclusion list."""
    from discolike.errors import ValidationError

    domain_list: list[str] = []
    if domains:
        domain_list = [d.strip() for d in domains.split(",") if d.strip()]
    elif input_file:
        with open(input_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    # Handle CSV (take first column)
                    domain_list.append(line.split(",")[0].strip())
    else:
        raise ValidationError("Provide --domains or --input")

    client = get_client(ctx)
    cli_ctx = _get_context(ctx)
    result = client.save_exclusion(name, domain_list)

    cli_ctx.output.render(
        result,
        title="Saved Exclusion List",
        cost=client.cost_tracker.last_call,
    )
    cli_ctx.output.success(f"Saved {len(domain_list)} domains as '{name}'")
