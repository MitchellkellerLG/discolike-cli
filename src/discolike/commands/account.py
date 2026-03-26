"""Account status and usage commands."""

from __future__ import annotations

import click

from discolike.cli import _get_context, get_client
from discolike.errors import handle_errors


@click.group("account")
def account() -> None:
    """Check account status and usage."""


@account.command("status")
@handle_errors
@click.pass_context
def account_status(ctx: click.Context) -> None:
    """Show account plan, spend, and remaining budget."""
    client = get_client(ctx)
    cli_ctx = _get_context(ctx)
    result = client.account_status()

    cli_ctx.output.render(
        result,
        title="Account Status",
        cost=client.cost_tracker.last_call,
        cached=False,
    )


@account.command("usage")
@handle_errors
@click.pass_context
def account_usage(ctx: click.Context) -> None:
    """Show detailed monthly usage breakdown."""
    client = get_client(ctx)
    cli_ctx = _get_context(ctx)
    result = client.usage()

    cli_ctx.output.render(
        result,
        title="Monthly Usage",
        cost=client.cost_tracker.last_call,
    )
