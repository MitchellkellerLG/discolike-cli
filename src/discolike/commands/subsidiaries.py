"""Corporate hierarchy / subsidiaries command (Enterprise plan required)."""

from __future__ import annotations

import click

from discolike.cli import _get_context, get_client
from discolike.commands.plan_gate import require_plan
from discolike.errors import handle_errors


@click.command("subsidiaries")
@click.argument("domain")
@handle_errors
@require_plan("subsidiaries")
@click.pass_context
def subsidiaries(ctx: click.Context, domain: str) -> None:
    """Get corporate hierarchy and subsidiaries for a domain."""
    client = get_client(ctx)
    cli_ctx = _get_context(ctx)
    result = client.subsidiaries(domain)

    cli_ctx.output.render(
        result,
        title=f"Subsidiaries: {domain}",
        cost=client.cost_tracker.last_call,
    )
