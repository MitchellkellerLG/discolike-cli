"""DiscoGen command group -- AI-powered domain and persona enrichment."""

from __future__ import annotations

import json
import sys
from typing import Any

import click
from rich.console import Console
from rich.live import Live
from rich.table import Table

from discolike.async_tasks import AsyncTaskManager
from discolike.cli import _get_context, get_client
from discolike.domain_input import read_domains, validate_domain_count
from discolike.errors import handle_errors


def _make_interim_handler(console: Console):
    """Create a Rich Live interim results handler.

    Returns (live_context, handler_fn). The handler appends new rows to the
    table as interim_results grow with each poll iteration.
    """
    seen_count = 0
    table = Table(title="Interim Results")
    table.add_column("Domain")
    table.add_column("Result", max_width=60)
    live = Live(table, console=console, refresh_per_second=2)

    def handler(result: dict[str, Any], attempt: int, elapsed: float) -> None:
        nonlocal seen_count
        interim = result.get("interim_results", [])
        for item in interim[seen_count:]:
            table.add_row(
                item.get("domain", "?"),
                str(item.get("result", ""))[:60],
            )
        seen_count = len(interim)

    return live, handler


def _show_cost_estimate(
    cli_ctx: Any,
    item_count: int,
    item_label: str,
    context_mode: str,
    web_search: bool,
    estimate: Any,
) -> None:
    """Display a pre-flight cost estimate table to stderr."""
    table = Table(title="Cost Estimate", show_header=True)
    table.add_column("Field", style="dim")
    table.add_column("Value")
    table.add_row(item_label, str(item_count))
    table.add_row("Context mode", context_mode)
    table.add_row("Web search", "yes" if web_search else "no")
    table.add_row("Estimated cost", f"${float(estimate.total):.4f}")
    cli_ctx.output._stderr.print(table)


@click.group("discogen")
def discogen() -> None:
    """AI-powered domain and persona enrichment."""


@discogen.command("run")
@click.option("--prompt", required=True, help="Prompt to run against each domain")
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
def discogen_run(
    ctx: click.Context,
    prompt: str,
    input_file: str | None,
    domain: tuple[str, ...],
    context_mode: str,
    web_search: bool,
    auto_confirm: bool,
) -> None:
    """Run an LLM prompt against each domain in a list.

    Submits domains to the DiscoGen endpoint, polls for results,
    and displays them. Shows interim results as they arrive during
    long-running jobs.
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
    estimate = cli_ctx.cost_tracker.estimate("discogen", len(domains))
    _show_cost_estimate(cli_ctx, len(domains), "Domains", context_mode, web_search, estimate)

    # Step 4: Confirmation gate
    if auto_confirm:
        pass  # --yes flag bypasses confirmation
    elif sys.stdin.isatty():
        click.confirm("Proceed?", default=False, abort=True)
    else:
        raise click.UsageError("--yes flag required in non-interactive mode")

    # Step 5: Build submit params
    params: dict[str, Any] = {
        "prompt": prompt,
        "domains": domains,
        "context_mode": context_mode,
    }
    if web_search:
        params["web_search"] = True

    # Step 6: Submit task
    submit_resp = client.discogen_submit(params)
    task_id = submit_resp["task_id"]

    # Step 7: Save task to cache BEFORE polling (D-03: survivable on Ctrl+C)
    if cli_ctx.cache is not None:
        cli_ctx.cache.save_task(task_id, "discogen", json.dumps(params))

    # Step 8: Set up interim display and poll
    task_mgr = AsyncTaskManager(client, cli_ctx.cache)  # type: ignore[arg-type]

    if cli_ctx.output.is_tty:
        # TTY mode: use Rich Live table for interim results
        live, on_result_handler = _make_interim_handler(cli_ctx.output._stderr)
        with live:
            result = task_mgr.poll(task_id, on_result=on_result_handler)
    else:
        # Non-TTY mode: plain progress percentage to stderr
        def on_status(status: str, attempt: int, elapsed: float) -> None:
            progress = None
            # Progress info not available from status string alone
            print(f"[{elapsed:.0f}s] Status: {status}", file=sys.stderr)

        result = task_mgr.poll(task_id, on_result=lambda r, a, e: None)

    # Step 9: Render final results
    cli_ctx.output.render(
        result.get("results", []),
        title="DiscoGen Results",
        cost=cli_ctx.cost_tracker.last_call,
    )


@discogen.command("personas")
@click.option("--prompt", required=True, help="Prompt to run against each persona")
@click.option(
    "--input", "input_file",
    type=click.Path(exists=True),
    default=None,
    help="CSV or text file with persona IDs",
)
@click.option("--persona-id", "-p", multiple=True, help="Inline persona ID(s)")
@click.option(
    "--context-mode",
    type=click.Choice(["full", "company", "profile", "name_only"]),
    default="profile",
    help="Analysis context (full, company, profile, or name_only)",
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
def discogen_personas(
    ctx: click.Context,
    prompt: str,
    input_file: str | None,
    persona_id: tuple[str, ...],
    context_mode: str,
    web_search: bool,
    auto_confirm: bool,
) -> None:
    """Run an LLM prompt against each persona in a list.

    Submits persona IDs to the DiscoGen personas endpoint, polls for
    results, and displays them. Context modes differ from the run command:
    full, company, profile, or name_only.
    """
    client = get_client(ctx)
    cli_ctx = _get_context(ctx)

    # Step 1: Read and validate persona ID list
    # Reuse read_domains for file parsing (reads first-column / domain-column values)
    persona_ids = read_domains(input_file, persona_id)
    validate_domain_count(persona_ids)  # Same 10k cap applies

    # Step 2: Web search warning for large lists
    if web_search and len(persona_ids) > 50:
        cli_ctx.output.warning(
            f"Web search on {len(persona_ids)} personas -- this will significantly increase cost."
        )

    # Step 3: Pre-flight cost estimate
    estimate = cli_ctx.cost_tracker.estimate("discogen-personas", len(persona_ids))
    _show_cost_estimate(cli_ctx, len(persona_ids), "Personas", context_mode, web_search, estimate)

    # Step 4: Confirmation gate
    if auto_confirm:
        pass
    elif sys.stdin.isatty():
        click.confirm("Proceed?", default=False, abort=True)
    else:
        raise click.UsageError("--yes flag required in non-interactive mode")

    # Step 5: Build submit params
    params: dict[str, Any] = {
        "prompt": prompt,
        "persona_ids": persona_ids,
        "context_mode": context_mode,
    }
    if web_search:
        params["web_search"] = True

    # Step 6: Submit task
    submit_resp = client.discogen_personas_submit(params)
    task_id = submit_resp["task_id"]

    # Step 7: Save task to cache BEFORE polling
    if cli_ctx.cache is not None:
        cli_ctx.cache.save_task(task_id, "discogen-personas", json.dumps(params))

    # Step 8: Poll for results
    task_mgr = AsyncTaskManager(client, cli_ctx.cache)  # type: ignore[arg-type]

    if cli_ctx.output.is_tty:
        live, on_result_handler = _make_interim_handler(cli_ctx.output._stderr)
        with live:
            result = task_mgr.poll(task_id, on_result=on_result_handler)
    else:
        result = task_mgr.poll(task_id, on_result=lambda r, a, e: None)

    # Step 9: Render final results
    cli_ctx.output.render(
        result.get("results", []),
        title="DiscoGen Personas Results",
        cost=cli_ctx.cost_tracker.last_call,
    )
