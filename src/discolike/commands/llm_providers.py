"""BYOM LLM provider configuration commands."""

from __future__ import annotations

import click

from discolike.cli import _get_context, get_client
from discolike.errors import handle_errors


@click.group("llm-providers")
def llm_providers() -> None:
    """Manage BYOM LLM provider configuration."""


@llm_providers.command("list")
@handle_errors
@click.pass_context
def llm_providers_list(ctx: click.Context) -> None:
    """List configured LLM providers."""
    client = get_client(ctx)
    cli_ctx = _get_context(ctx)
    result = client.llm_providers_list()

    cli_ctx.output.render(
        result,
        title="LLM Providers",
        cost=client.cost_tracker.last_call,
    )


@llm_providers.command("set")
@click.option("--provider", required=True, help="Provider name (e.g. openai, anthropic)")
@click.option("--api-key", required=True, help="API key for the provider")
@click.option("--model", default=None, help="Default model (e.g. gpt-4o)")
@click.option("--base-url", default=None, help="Custom base URL for self-hosted")
@handle_errors
@click.pass_context
def llm_providers_set(
    ctx: click.Context,
    provider: str,
    api_key: str,
    model: str | None,
    base_url: str | None,
) -> None:
    """Set or update an LLM provider configuration."""
    client = get_client(ctx)
    cli_ctx = _get_context(ctx)

    config: dict[str, object] = {"api_key": api_key}
    if model:
        config["model"] = model
    if base_url:
        config["base_url"] = base_url

    result = client.llm_providers_set(provider, config)

    cli_ctx.output.render(
        result,
        title=f"LLM Provider: {provider}",
        cost=client.cost_tracker.last_call,
    )
