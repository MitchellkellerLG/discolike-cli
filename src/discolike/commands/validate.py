"""Validate command -- ICP validation against a domain list."""

from __future__ import annotations

import json
import sys
from typing import Any

import click
from rich.table import Table

from discolike.async_tasks import AsyncTaskManager
from discolike.cli import _get_context, get_client
from discolike.domain_input import read_domains, validate_domain_count
from discolike.errors import handle_errors

# Sort order constants for Fit + Confidence
_FIT_ORDER = {"yes": 0, "partial": 1, "no": 2}
_CONF_ORDER = {"high": 0, "medium": 1, "low": 2}


def _sort_key(row: dict[str, Any]) -> tuple[int, int]:
    """Compound sort key for ICP validation results.

    Sort order:
    - yes+high, yes+medium, yes+low
    - partial+high, partial+medium, partial+low
    - no+low, no+medium, no+high (inverse confidence for "no" results)
    """
    fit = row.get("Fit", "no").lower()
    conf = row.get("Confidence", "low").lower()
    if fit == "no":
        # For "no" results, higher confidence goes last
        return (2, {"high": 2, "medium": 1, "low": 0}.get(conf, 1))
    return (_FIT_ORDER.get(fit, 2), _CONF_ORDER.get(conf, 1))


@click.command("validate")
@click.option("--icp", "icp_text", required=True, help="ICP description text")
@click.option(
    "--input", "input_file",
    type=click.Path(exists=True),
    default=None,
    help="CSV or text file with domains",
)
@click.option("--domain", "-d", multiple=True, help="Inline domain(s)")
@click.option(
    "--context-mode",
    type=click.Choice(["website", "profile", "domain"]),
    default="website",
    help="Analysis context (website, profile, or domain)",
)
@click.option(
    "--web-search",
    is_flag=True,
    default=False,
    help="Enable web search enrichment (increases cost)",
)
@click.option(
    "--yes",
    "auto_confirm",
    is_flag=True,
    default=False,
    help="Skip confirmation prompt (required in non-interactive mode)",
)
@handle_errors
@click.pass_context
def validate(
    ctx: click.Context,
    icp_text: str,
    input_file: str | None,
    domain: tuple[str, ...],
    context_mode: str,
    web_search: bool,
    auto_confirm: bool,
) -> None:
    """Score domains against an ICP description.

    Submits a list of domains to the DiscoLike ICP validation endpoint,
    polls for results, and displays them sorted by fit (yes > partial > no)
    and confidence (high > medium > low for yes/partial, inverse for no).
    """
    client = get_client(ctx)
    cli_ctx = _get_context(ctx)

    # Step 1: Read and validate domain list
    domains = read_domains(input_file, domain)
    validate_domain_count(domains)

    # Step 2: Web search warning for large lists
    if web_search and len(domains) > 50:
        cli_ctx.output.warning(
            f"Web search on {len(domains)} domains -- this will significantly increase cost."
        )

    # Step 3: Pre-flight cost estimate
    estimate = cli_ctx.cost_tracker.estimate("validate/icp", len(domains))
    _show_cost_estimate(cli_ctx, domains, context_mode, web_search, estimate)

    # Step 4: Confirmation gate
    if auto_confirm:
        pass  # --yes flag bypasses confirmation
    elif sys.stdin.isatty():
        click.confirm("Proceed with validation?", default=False, abort=True)
    else:
        raise click.UsageError("--yes flag required in non-interactive mode")

    # Step 5: Build submit params
    params: dict[str, Any] = {
        "icp_text": icp_text,
        "domains": domains,
        "context_mode": context_mode,
    }
    if web_search:
        params["web_search"] = True

    # Step 6: Submit task
    submit_resp = client.validate_icp_submit(params)
    task_id = submit_resp["task_id"]

    # Step 7: Save task to cache BEFORE polling (D-03: survivable on Ctrl+C)
    if cli_ctx.cache is not None:
        cli_ctx.cache.save_task(task_id, "validate/icp", json.dumps(params))

    # Step 8: Poll for results
    task_mgr = AsyncTaskManager(client, cli_ctx.cache)  # type: ignore[arg-type]
    result = task_mgr.poll(task_id)

    # Step 9: Normalize results dict -> list of rows
    raw_results = result.get("results", {})
    if isinstance(raw_results, dict):
        rows = [{"domain": k, **v} for k, v in raw_results.items()]
    elif isinstance(raw_results, list):
        rows = raw_results
    else:
        rows = []

    # Step 10: Sort results
    sorted_rows = sorted(rows, key=_sort_key)

    # Step 11: Render
    cli_ctx.output.render(
        sorted_rows,
        title="ICP Validation Results",
        columns=["domain", "Fit", "Confidence", "Reasoning"],
        cost=cli_ctx.cost_tracker.last_call,
    )


def _show_cost_estimate(
    cli_ctx: Any,
    domains: list[str],
    context_mode: str,
    web_search: bool,
    estimate: Any,
) -> None:
    """Display a pre-flight cost estimate table to stderr."""
    table = Table(title="Cost Estimate", show_header=True)
    table.add_column("Field", style="dim")
    table.add_column("Value")
    table.add_row("Domains", str(len(domains)))
    table.add_row("Context mode", context_mode)
    table.add_row("Web search", "yes" if web_search else "no")
    table.add_row("Estimated cost", f"${float(estimate.total):.4f}")
    cli_ctx.output._stderr.print(table)
