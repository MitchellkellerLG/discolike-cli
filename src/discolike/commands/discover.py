"""Discovery commands: count and discover with shared filters."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click

from discolike.cli import _get_context, get_client
from discolike.constants import CATEGORIES, VARIANCE_CHOICES
from discolike.errors import handle_errors


def discovery_filters(f: Any) -> Any:
    """Shared Click options for discovery filter parameters."""
    decorators = [
        # Positive filters
        click.option("--domain", "-d", multiple=True, help="Seed domain(s) (up to 10)"),
        click.option("--icp-text", type=str, default=None, help="Natural language ICP description"),
        click.option(
            "--phrase",
            "phrase_match",
            multiple=True,
            help="Exact homepage phrase (OR logic, up to 20)",
        ),
        click.option("--country", multiple=True, help="ISO alpha-2 country code(s)"),
        click.option("--state", multiple=True, help="State/province code(s)"),
        click.option(
            "--employees",
            "employee_range",
            type=str,
            default=None,
            help='Employee range "min,max"',
        ),
        click.option(
            "--category",
            multiple=True,
            type=click.Choice(CATEGORIES, case_sensitive=False),
            help="Industry category",
        ),
        click.option("--language", multiple=True, help="ISO-639-2 language code(s)"),
        click.option("--social", multiple=True, help="Social platform filter"),
        click.option(
            "--min-score",
            "min_digital_footprint",
            type=int,
            default=None,
            help="Min footprint score (0-800)",
        ),
        click.option(
            "--max-score",
            "max_digital_footprint",
            type=int,
            default=None,
            help="Max footprint score (0-800)",
        ),
        click.option(
            "--min-similarity", type=int, default=None, help="Min similarity (0-99)"
        ),
        click.option(
            "--start-date", type=str, default=None, help="Company start date (YYYY-MM-DD)"
        ),
        # Negation filters
        click.option("--negate-domain", multiple=True, help="Exclude domain(s)"),
        click.option("--negate-icp-text", type=str, default=None, help="Negate ICP text"),
        click.option("--negate-country", multiple=True, help="Exclude country(s)"),
        click.option(
            "--negate-category",
            multiple=True,
            type=click.Choice(CATEGORIES, case_sensitive=False),
            help="Exclude category",
        ),
        click.option(
            "--negate-phrase",
            "negate_phrase_match",
            multiple=True,
            help="Negate phrase match",
        ),
        click.option("--negate-language", multiple=True, help="Exclude language(s)"),
        click.option("--negate-social", multiple=True, help="Exclude social platform(s)"),
        # Special flags
        click.option(
            "--auto-icp/--no-auto-icp",
            "auto_icp_text",
            default=False,
            help="Auto-generate ICP text",
        ),
        click.option(
            "--auto-phrases/--no-auto-phrases",
            "auto_phrase_match",
            default=False,
            help="Auto-generate phrases",
        ),
        click.option(
            "--enhanced/--no-enhanced", default=False, help="AI-powered enhancement"
        ),
        click.option(
            "--include-seeds/--no-include-seeds",
            "include_search_domains",
            default=False,
            help="Include seeds in results",
        ),
        click.option(
            "--redirect/--no-redirect", default=False, help="Include redirecting domains"
        ),
        click.option(
            "--variance",
            type=click.Choice(VARIANCE_CHOICES, case_sensitive=False),
            default="UNRESTRICTED",
            help="Result diversity",
        ),
        click.option(
            "--consensus", type=int, default=1, help="Search vector consensus (1-20)"
        ),
    ]
    for decorator in reversed(decorators):
        f = decorator(f)
    return f


# Mapping from Click kwarg names to API filter parameter names
_FILTER_MAP: dict[str, str] = {
    "domain": "domain",
    "icp_text": "icp_text",
    "phrase_match": "phrase_match",
    "country": "country",
    "state": "state",
    "employee_range": "employee_range",
    "category": "category",
    "language": "language",
    "social": "social",
    "min_digital_footprint": "min_digital_footprint",
    "max_digital_footprint": "max_digital_footprint",
    "min_similarity": "min_similarity",
    "start_date": "start_date",
    "negate_domain": "negate_domain",
    "negate_icp_text": "negate_icp_text",
    "negate_country": "negate_country",
    "negate_category": "negate_category",
    "negate_phrase_match": "negate_phrase_match",
    "negate_language": "negate_language",
    "negate_social": "negate_social",
    "auto_icp_text": "auto_icp_text",
    "auto_phrase_match": "auto_phrase_match",
    "enhanced": "enhanced",
    "include_search_domains": "include_search_domains",
    "redirect": "redirect",
    "variance": "variance",
    "consensus": "consensus",
}

# Keys whose non-truthy default should NOT be sent
_SKIP_DEFAULTS = {
    "auto_icp_text",
    "auto_phrase_match",
    "enhanced",
    "include_search_domains",
    "redirect",
}


def collect_filters(**kwargs: Any) -> dict[str, Any]:
    """Build API filter dict from Click kwargs. Skips empty/None/default values."""
    filters: dict[str, Any] = {}
    for click_name, api_name in _FILTER_MAP.items():
        val = kwargs.get(click_name)
        if val is None:
            continue
        if isinstance(val, tuple):
            if not val:  # empty tuple from Click multiple=True
                continue
            val = list(val)
        if click_name in _SKIP_DEFAULTS and val is False:
            continue
        if click_name == "variance" and val == "UNRESTRICTED":
            continue  # API default
        if click_name == "consensus" and val == 1:
            continue  # API default
        filters[api_name] = val
    return filters


@click.command("count")
@discovery_filters
@handle_errors
@click.pass_context
def count(ctx: click.Context, **kwargs: Any) -> None:
    """Count domains matching filters (no records returned)."""
    client = get_client(ctx)
    cli_ctx = _get_context(ctx)
    filters = collect_filters(**kwargs)

    result = client.count(filters)

    # Threshold warnings
    if result.count < 50:
        cli_ctx.output.warning(
            f"Only {result.count} matches. Consider loosening filters for better discovery."
        )
    elif result.count > 10_000:
        cli_ctx.output.warning(
            f"{result.count:,} matches. Consider tightening filters to improve relevance."
        )

    cli_ctx.output.render(
        result,
        title="Domain Count",
        cost=client.cost_tracker.last_call,
    )


@click.command("discover")
@discovery_filters
@click.option("--max-records", type=int, default=10, help="Max records to return (default: 10)")
@click.option(
    "--discover-fields",
    "field_list",
    type=str,
    default=None,
    help="Comma-separated fields to return",
)
@click.option(
    "--output", "-o", type=click.Path(), default=None, help="Save results to file (CSV/JSON)"
)
@click.option(
    "--exclude", type=str, default=None, help="Saved query ID to exclude domains from"
)
@handle_errors
@click.pass_context
def discover(
    ctx: click.Context,
    max_records: int,
    field_list: str | None,
    output: str | None,
    exclude: str | None,
    **kwargs: Any,
) -> None:
    """Find companies similar to seed domains or ICP description."""
    client = get_client(ctx)
    cli_ctx = _get_context(ctx)
    filters = collect_filters(**kwargs)
    fields = [f.strip() for f in field_list.split(",")] if field_list else None

    result = client.discover(
        filters=filters,
        max_records=max_records,
        fields=fields,
        exclude_query_id=exclude,
    )

    # Save to file if requested
    if output and result.records:
        output_path = Path(output)
        records_dicts = [r.model_dump(mode="json") for r in result.records]
        if output_path.suffix.lower() == ".csv":
            from discolike.exporters.csv_export import export_csv

            export_csv(records_dicts, output_path)
        else:
            from discolike.exporters.json_export import export_json

            export_json({"records": records_dicts, "count": result.count}, output_path)
        cli_ctx.output.success(f"Saved {len(result.records)} records to {output}")

    cli_ctx.output.render(
        result,
        title=f"Discovery Results ({result.count} matches)",
        cost=client.cost_tracker.last_call,
    )
