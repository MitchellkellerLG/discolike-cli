"""Company name to domain matching (Team+ plan required)."""

from __future__ import annotations

import click

from discolike.cli import _get_context, get_client
from discolike.commands.plan_gate import require_plan
from discolike.domain_input import read_domains, validate_domain_count
from discolike.errors import handle_errors


@click.group("match", invoke_without_command=True)
@click.argument("company_name", required=False)
@handle_errors
@require_plan("match")
@click.pass_context
def match(ctx: click.Context, company_name: str | None) -> None:
    """Resolve a company name to its domain.

    Subcommands:
      discolike match bulk --input names.csv  Batch-resolve names
    """
    if ctx.invoked_subcommand is not None:
        return

    if not company_name:
        raise click.UsageError("Provide a company name, or use: discolike match bulk --input FILE")

    client = get_client(ctx)
    cli_ctx = _get_context(ctx)
    result = client.match(company_name)

    cli_ctx.output.render(
        result,
        title=f"Match: {company_name}",
        cost=client.cost_tracker.last_call,
    )


@match.command("bulk")
@click.option(
    "--input", "input_file",
    type=click.Path(exists=True),
    default=None,
    help="CSV or text file with company names",
)
@click.option("--name", "-n", multiple=True, help="Inline company name(s)")
@click.option(
    "--yes",
    "auto_confirm",
    is_flag=True,
    default=False,
    help="Skip confirmation prompt",
)
@handle_errors
@require_plan("bulk_match")
@click.pass_context
def match_bulk(
    ctx: click.Context,
    input_file: str | None,
    name: tuple[str, ...],
    auto_confirm: bool,
) -> None:
    """Batch-resolve company names to domains.

    Provide names via --input FILE, --name flags, or pipe via stdin.
    """
    import sys

    client = get_client(ctx)
    cli_ctx = _get_context(ctx)

    # Reuse domain_input for reading names from file/stdin
    names = read_domains(input_file, name)
    validate_domain_count(names)

    if not names:
        raise click.UsageError("No names provided. Use --input, --name, or stdin.")

    # Confirmation for large batches
    if len(names) > 100 and not auto_confirm and sys.stdin.isatty():
        click.confirm(
            f"Match {len(names)} company names? Estimated cost: ~${0.18 * len(names):.2f}",
            default=False,
            abort=True,
        )

    cli_ctx.output.status(f"Matching {len(names)} company names...")
    result = client.bulk_match(names)

    cli_ctx.output.render(
        result,
        title=f"Bulk Match ({len(names)} names)",
        cost=client.cost_tracker.last_call,
    )
