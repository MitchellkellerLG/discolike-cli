"""BYOS search provider configuration commands."""

from __future__ import annotations

import click

from discolike.cli import _get_context, get_client
from discolike.errors import handle_errors


@click.group("search-providers")
def search_providers() -> None:
    """Manage BYOS search provider configuration."""


@search_providers.command("list")
@handle_errors
@click.pass_context
def search_providers_list(ctx: click.Context) -> None:
    """List configured search providers."""
    client = get_client(ctx)
    cli_ctx = _get_context(ctx)
    result = client.search_providers_list()

    cli_ctx.output.render(
        result,
        title="Search Providers",
        cost=client.cost_tracker.last_call,
    )


@search_providers.command("set")
@click.option("--provider", required=True, help="Provider name (e.g. serper, brave)")
@click.option("--api-key", required=True, help="API key for the provider")
@click.option("--base-url", default=None, help="Custom base URL for self-hosted")
@handle_errors
@click.pass_context
def search_providers_set(
    ctx: click.Context,
    provider: str,
    api_key: str,
    base_url: str | None,
) -> None:
    """Set or update a search provider configuration."""
    client = get_client(ctx)
    cli_ctx = _get_context(ctx)

    config: dict[str, object] = {"api_key": api_key}
    if base_url:
        config["base_url"] = base_url

    result = client.search_providers_set(provider, config)

    cli_ctx.output.render(
        result,
        title=f"Search Provider: {provider}",
        cost=client.cost_tracker.last_call,
    )
