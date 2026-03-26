"""Enrichment commands: profile, score, growth."""

from __future__ import annotations

import click

from discolike.cli import _get_context, get_client
from discolike.errors import handle_errors


@click.command("profile")
@click.argument("domain")
@click.option("--fields", "field_list", type=str, default=None, help="Comma-separated fields")
@click.option("--output", "-o", type=click.Path(), default=None, help="Save to file")
@handle_errors
@click.pass_context
def profile(ctx: click.Context, domain: str, field_list: str | None, output: str | None) -> None:
    """Get enriched business profile for a domain."""
    client = get_client(ctx)
    cli_ctx = _get_context(ctx)
    fields = [f.strip() for f in field_list.split(",")] if field_list else None
    result = client.business_profile(domain, fields=fields)

    if output:
        from discolike.exporters.json_export import export_json

        export_json(result.model_dump(mode="json"), output)
        cli_ctx.output.success(f"Saved to {output}")
    else:
        cli_ctx.output.render(
            result,
            title=f"Business Profile: {domain}",
            cost=client.cost_tracker.last_call,
        )


@click.command("score")
@click.argument("domain")
@handle_errors
@click.pass_context
def score(ctx: click.Context, domain: str) -> None:
    """Get digital footprint score for a domain."""
    client = get_client(ctx)
    cli_ctx = _get_context(ctx)
    result = client.score(domain)

    cli_ctx.output.render(
        result,
        title=f"Digital Footprint Score: {domain}",
        cost=client.cost_tracker.last_call,
    )


@click.command("growth")
@click.argument("domain")
@handle_errors
@click.pass_context
def growth(ctx: click.Context, domain: str) -> None:
    """Get growth metrics for a domain."""
    client = get_client(ctx)
    cli_ctx = _get_context(ctx)
    result = client.growth(domain)

    cli_ctx.output.render(
        result,
        title=f"Growth Metrics: {domain}",
        cost=client.cost_tracker.last_call,
    )
