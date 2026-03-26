"""Tech stack / vendor data command (Team+ plan required)."""

from __future__ import annotations

import click

from discolike.cli import _get_context, get_client
from discolike.commands.plan_gate import require_plan
from discolike.errors import handle_errors


@click.command("vendors")
@click.argument("domain")
@handle_errors
@require_plan("vendors")
@click.pass_context
def vendors(ctx: click.Context, domain: str) -> None:
    """Get tech stack / vendor data for a domain."""
    client = get_client(ctx)
    cli_ctx = _get_context(ctx)
    result = client.vendors(domain)

    cli_ctx.output.render(
        result,
        title=f"Vendors: {domain}",
        cost=client.cost_tracker.last_call,
    )
