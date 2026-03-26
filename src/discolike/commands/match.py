"""Company name to domain matching (Team+ plan required)."""

from __future__ import annotations

import click

from discolike.cli import _get_context, get_client
from discolike.commands.plan_gate import require_plan
from discolike.errors import handle_errors


@click.command("match")
@click.argument("company_name")
@handle_errors
@require_plan("match")
@click.pass_context
def match(ctx: click.Context, company_name: str) -> None:
    """Resolve a company name to its domain."""
    client = get_client(ctx)
    cli_ctx = _get_context(ctx)
    result = client.match(company_name)

    cli_ctx.output.render(
        result,
        title=f"Match: {company_name}",
        cost=client.cost_tracker.last_call,
    )
