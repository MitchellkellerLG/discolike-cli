"""Contacts search command (Team+ plan required)."""

from __future__ import annotations

import click

from discolike.cli import _get_context, get_client
from discolike.commands.plan_gate import require_plan
from discolike.errors import handle_errors


@click.command("contacts")
@click.option("--domain", required=True, help="Company domain to search")
@click.option("--title", type=str, default=None, help="Job title filter")
@click.option("--max-records", type=int, default=25, help="Max contacts to return")
@click.option("--output", "-o", type=click.Path(), default=None, help="Save to file")
@handle_errors
@require_plan("contacts")
@click.pass_context
def contacts(
    ctx: click.Context,
    domain: str,
    title: str | None,
    max_records: int,
    output: str | None,
) -> None:
    """Search for B2B contacts at a company."""
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
