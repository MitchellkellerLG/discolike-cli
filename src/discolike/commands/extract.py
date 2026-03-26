"""Extract website text command."""

from __future__ import annotations

import click

from discolike.cli import _get_context, get_client
from discolike.errors import handle_errors


@click.command("extract")
@click.argument("domain")
@handle_errors
@click.pass_context
def extract(ctx: click.Context, domain: str) -> None:
    """Extract cached website text for a domain."""
    client = get_client(ctx)
    cli_ctx = _get_context(ctx)
    result = client.extract(domain)

    cli_ctx.output.render(
        result,
        title=f"Website Text: {domain}",
        cost=client.cost_tracker.last_call,
    )
