"""Session cost tracking command."""

from __future__ import annotations

from decimal import Decimal

import click

from discolike.cli import _get_context
from discolike.errors import handle_errors


@click.command("costs")
@click.option("--reset", is_flag=True, help="Reset session cost counter")
@handle_errors
@click.pass_context
def costs(ctx: click.Context, reset: bool) -> None:
    """Show session cost breakdown."""
    cli_ctx = _get_context(ctx)

    if cli_ctx.cache is None:
        click.echo("No cache available (--no-cache mode). Cost tracking requires cache.")
        return

    if reset:
        count = cli_ctx.cache.reset_costs()
        click.echo(f"Reset {count} cost entries.")
        return

    entries = cli_ctx.cache.get_session_costs()
    if not entries:
        click.echo("No costs recorded in this session.")
        return

    total = Decimal("0")
    for entry in entries:
        total += Decimal(entry["total"])

    if cli_ctx.json_output:
        from discolike.output import click_echo_json

        click_echo_json({"costs": entries, "total": float(total), "count": len(entries)})
    else:
        click.echo("Session Costs")
        click.echo("=" * 50)
        for entry in entries:
            click.echo(
                f"  {entry['endpoint']:<35} ${Decimal(entry['total']):>8.4f}  "
                f"({entry['records_returned']} records)"
            )
        click.echo("=" * 50)
        click.echo(f"  {'Total':<35} ${total:>8.4f}  ({len(entries)} calls)")
