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
@click.option("--integration-name", required=True, help="User-friendly name for this integration")
@click.option("--provider", required=True, help="Provider name (e.g. openai, anthropic, deepseek)")
@click.option("--api-key", required=True, help="API key for the provider")
@click.option("--model-name", required=True, help="Model name in LiteLLM format (e.g. openai/gpt-4o, deepseek/deepseek-chat)")
@click.option("--base-url", default=None, help="Custom base URL for self-hosted")
@handle_errors
@click.pass_context
def llm_providers_set(
    ctx: click.Context,
    integration_name: str,
    provider: str,
    api_key: str,
    model_name: str,
    base_url: str | None,
) -> None:
    """Set or update an LLM provider configuration."""
    client = get_client(ctx)
    cli_ctx = _get_context(ctx)

    config: dict[str, object] = {
        "integration_name": integration_name,
        "api_key": api_key,
        "model_name": model_name,
    }
    if base_url:
        config["base_url"] = base_url

    result = client.llm_providers_set(provider, config)

    cli_ctx.output.render(
        result,
        title=f"LLM Provider: {provider}",
        cost=client.cost_tracker.last_call,
    )
