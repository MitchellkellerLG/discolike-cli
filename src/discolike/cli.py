"""Click entry point for DiscoLike CLI."""

from __future__ import annotations

from dataclasses import dataclass, field

import click

from discolike import __version__
from discolike.cache import CacheManager
from discolike.client import DiscoLikeClient
from discolike.config import get_api_key
from discolike.cost import CostTracker
from discolike.errors import AuthError
from discolike.output import OutputManager


@dataclass
class CliContext:
    """Shared context for all CLI commands."""

    client: DiscoLikeClient | None = None
    output: OutputManager = field(default_factory=OutputManager)
    cost_tracker: CostTracker = field(default_factory=CostTracker)
    cache: CacheManager | None = None
    json_output: bool = False
    csv_output: bool = False
    dry_run: bool = False
    no_cache: bool = False
    quiet: bool = False
    fields: list[str] | None = None


def _get_context(ctx: click.Context) -> CliContext:
    """Get the CliContext from a Click context."""
    return ctx.ensure_object(CliContext)


@click.group()
@click.version_option(version=__version__, prog_name="discolike")
@click.option("--json", "json_output", is_flag=True, help="Force JSON output")
@click.option("--csv", "csv_output", is_flag=True, help="Force CSV output")
@click.option("--fields", type=str, default=None, help="Comma-separated field list")
@click.option("--quiet", "-q", is_flag=True, help="Suppress progress messages")
@click.option("--no-cache", is_flag=True, help="Bypass local cache")
@click.option("--dry-run", is_flag=True, help="Show estimated cost without API calls")
@click.pass_context
def cli(
    ctx: click.Context,
    json_output: bool,
    csv_output: bool,
    fields: str | None,
    quiet: bool,
    no_cache: bool,
    dry_run: bool,
) -> None:
    """DiscoLike -- B2B company discovery from the terminal."""
    parsed_fields = [f.strip() for f in fields.split(",")] if fields else None

    cli_ctx = CliContext(
        json_output=json_output,
        csv_output=csv_output,
        dry_run=dry_run,
        no_cache=no_cache,
        quiet=quiet,
        fields=parsed_fields,
        output=OutputManager(
            json_output=json_output,
            csv_output=csv_output,
            fields=parsed_fields,
            quiet=quiet,
        ),
    )

    # Lazy client init — only create when a command needs it
    # Config commands don't need the client
    cli_ctx.cost_tracker = CostTracker()
    if not no_cache:
        cli_ctx.cache = CacheManager()

    ctx.obj = cli_ctx


def get_client(ctx: click.Context) -> DiscoLikeClient:
    """Lazily initialize and return the API client."""
    cli_ctx = _get_context(ctx)
    if cli_ctx.client is None:
        try:
            api_key = get_api_key()
        except AuthError:
            raise
        cli_ctx.client = DiscoLikeClient(
            api_key=api_key,
            cache=cli_ctx.cache if not cli_ctx.no_cache else None,
            cost_tracker=cli_ctx.cost_tracker,
            dry_run=cli_ctx.dry_run,
        )
    return cli_ctx.client


# Import and register all command groups
from discolike.commands.account import account  # noqa: E402
from discolike.commands.config_cmd import config  # noqa: E402
from discolike.commands.costs_cmd import costs  # noqa: E402
from discolike.commands.discover import count, discover  # noqa: E402
from discolike.commands.enrich import growth, profile, score  # noqa: E402
from discolike.commands.extract import extract  # noqa: E402
from discolike.commands.saved import saved  # noqa: E402

cli.add_command(config)
cli.add_command(account)
cli.add_command(extract)
cli.add_command(count)
cli.add_command(discover)
cli.add_command(profile)
cli.add_command(score)
cli.add_command(growth)
cli.add_command(saved)
cli.add_command(costs)

from discolike.commands.append import append  # noqa: E402
from discolike.commands.contacts import contacts  # noqa: E402
from discolike.commands.match import match  # noqa: E402
from discolike.commands.subsidiaries import subsidiaries  # noqa: E402
from discolike.commands.vendors import vendors  # noqa: E402
from discolike.commands.workflow import workflow  # noqa: E402

cli.add_command(contacts)
cli.add_command(match)
cli.add_command(append)
cli.add_command(vendors)
cli.add_command(subsidiaries)
cli.add_command(workflow)
