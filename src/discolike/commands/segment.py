"""Segment command -- auto-cluster domains (Pro+ plan required)."""

from __future__ import annotations

import json
import sys
from typing import Any

import click

from discolike.async_tasks import AsyncTaskManager
from discolike.cli import _get_context, get_client
from discolike.commands.plan_gate import require_plan
from discolike.domain_input import read_domains, validate_domain_count
from discolike.errors import handle_errors


@click.command("segment")
@click.option(
    "--input", "input_file",
    type=click.Path(exists=True),
    default=None,
    help="CSV or text file with domains",
)
@click.option("--domain", "-d", multiple=True, help="Inline domain(s)")
@click.option(
    "--yes",
    "auto_confirm",
    is_flag=True,
    default=False,
    help="Skip confirmation prompt (required in non-interactive mode)",
)
@handle_errors
@require_plan("segment")
@click.pass_context
def segment(
    ctx: click.Context,
    input_file: str | None,
    domain: tuple[str, ...],
    auto_confirm: bool,
) -> None:
    """Auto-cluster domains into market segments.

    Submits a list of domains to the DiscoLike segment endpoint,
    polls for results, and displays clusters with member domains.
    """
    client = get_client(ctx)
    cli_ctx = _get_context(ctx)

    # Step 1: Read and validate domain list
    domains = read_domains(input_file, domain)
    validate_domain_count(domains)

    # Step 2: Pre-flight cost estimate
    estimate = cli_ctx.cost_tracker.estimate("segment", len(domains))
    _show_segment_cost_estimate(cli_ctx, len(domains), estimate)

    # Step 3: Confirmation gate
    if auto_confirm:
        pass
    elif sys.stdin.isatty():
        click.confirm("Proceed with segmentation?", default=False, abort=True)
    else:
        raise click.UsageError("--yes flag required in non-interactive mode")

    # Step 4: Submit task
    params: dict[str, Any] = {"domains": domains}
    submit_resp = client.segment_submit(params)
    task_id = submit_resp["task_id"]

    # Step 5: Save task to cache BEFORE polling
    if cli_ctx.cache is not None:
        cli_ctx.cache.save_task(task_id, "segment", json.dumps(params))

    # Step 6: Poll for results (segment rate limit: 2 req/min)
    task_mgr = AsyncTaskManager(client, cli_ctx.cache)  # type: ignore[arg-type]
    result = task_mgr.poll(
        task_id,
        initial_interval=5.0,
        max_interval=30.0,
        max_elapsed=600.0,
    )

    # Step 7: Render results
    clusters = result.get("results", result.get("clusters", []))
    if isinstance(clusters, dict):
        rows = [
            {"cluster": k, "domains": ", ".join(v) if isinstance(v, list) else str(v)}
            for k, v in clusters.items()
        ]
    elif isinstance(clusters, list):
        rows = clusters
    else:
        rows = []

    cli_ctx.output.render(
        rows,
        title="Segment Results",
        cost=cli_ctx.cost_tracker.last_call,
    )


def _show_segment_cost_estimate(
    cli_ctx: Any,
    domain_count: int,
    estimate: Any,
) -> None:
    """Display a pre-flight cost estimate for segmentation."""
    from rich.table import Table

    table = Table(title="Cost Estimate", show_header=True)
    table.add_column("Field", style="dim")
    table.add_column("Value")
    table.add_row("Domains", str(domain_count))
    table.add_row("Rate limit", "2 req/min")
    table.add_row("Estimated cost", f"${float(estimate.total):.4f}")
    cli_ctx.output._stderr.print(table)
