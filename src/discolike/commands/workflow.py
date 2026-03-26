"""Composite workflow commands."""

from __future__ import annotations

import datetime
import sys
from pathlib import Path
from typing import Any

import click
from rich.progress import Progress

from discolike.cli import _get_context, get_client
from discolike.errors import handle_errors
from discolike.exporters.csv_export import auto_csv_name, export_csv


@click.group("workflow")
def workflow() -> None:
    """Composite workflow commands."""


@workflow.command("discover")
@click.option("--seed", required=True, multiple=True, help="Seed domain(s)")
@click.option("--country", multiple=True, help="Country code(s)")
@click.option("--max-records", type=int, default=100, help="Max records for full discovery")
@click.option("--enrich-top", type=int, default=5, help="Enrich top N results with profiles")
@click.option("--output", "-o", type=click.Path(), default=None, help="Output CSV/JSON path")
@click.option("--save-exclusion", is_flag=True, help="Save results as exclusion list")
@click.option("--no-confirm", is_flag=True, help="Skip interactive prompts")
@handle_errors
@click.pass_context
def workflow_discover(
    ctx: click.Context,
    seed: tuple[str, ...],
    country: tuple[str, ...],
    max_records: int,
    enrich_top: int,
    output: str | None,
    save_exclusion: bool,
    no_confirm: bool,
) -> None:
    """Run the full 8-step discovery workflow."""
    client = get_client(ctx)
    cli_ctx = _get_context(ctx)
    out = cli_ctx.output

    seed_list = list(seed)
    primary_seed = seed_list[0]

    # Step 1: Account status
    out.status("Step 1/8: Checking account status...")
    status = client.account_status()
    if status.usage and status.usage.total_available_spend is not None:
        out.status(
            f"  Plan: {status.plan or 'unknown'} | "
            f"Budget remaining: ${status.usage.total_available_spend:.2f}"
        )
    _show_running_cost(out, client)

    # Step 2: Extract seed website text
    out.status(f"Step 2/8: Extracting website text for {primary_seed}...")
    extract_result = client.extract(primary_seed)
    text_preview = (extract_result.text or "")[:200]
    if text_preview:
        out.status(f"  Preview: {text_preview}...")
    _show_running_cost(out, client)

    # Step 3: Count matching domains
    filters: dict[str, Any] = {"domain": seed_list}
    if country:
        filters["country"] = list(country)

    out.status("Step 3/8: Counting matching domains...")
    count_result = client.count(filters)
    out.status(f"  Found {count_result.count:,} matching domains")
    _show_running_cost(out, client)

    if count_result.count == 0:
        out.warning("No matching domains found. Try different seeds or filters.")
        return

    # Step 4: Validation discover (10 records)
    out.status("Step 4/8: Validation discovery (10 records)...")
    validation = client.discover(filters=filters, max_records=10)
    out.status(f"  Got {len(validation.records)} validation records")

    if validation.records:
        out.render(validation, title="Validation Results (top 10)")

    _show_running_cost(out, client)

    # Interactive confirmation
    if not no_confirm and sys.stdin.isatty():
        if not click.confirm(
            "Results look good? Continue with full discovery?", default=True
        ):
            out.status("Workflow cancelled by user.")
            return

    # Step 5: Full discovery
    out.status(f"Step 5/8: Full discovery ({max_records} records)...")
    full_result = client.discover(filters=filters, max_records=max_records)
    out.status(f"  Got {len(full_result.records)} records")
    _show_running_cost(out, client)

    # Step 6: Enrich top N
    enriched_records: list[dict[str, Any]] = []
    if enrich_top > 0 and full_result.records:
        top_domains = [r.domain for r in full_result.records[:enrich_top]]
        out.status(f"Step 6/8: Enriching top {len(top_domains)} results...")
        for i, domain in enumerate(top_domains, 1):
            out.status(f"  Enriching {i}/{len(top_domains)}: {domain}")
            profile = client.business_profile(domain)
            enriched_records.append(profile.model_dump(mode="json"))
        _show_running_cost(out, client)
    else:
        out.status("Step 6/8: Skipping enrichment (enrich-top=0)")

    # Step 7: Export CSV
    all_records = [r.model_dump(mode="json") for r in full_result.records]
    # Merge enriched data into discovery records
    enriched_map = {r["domain"]: r for r in enriched_records}
    for record in all_records:
        if record["domain"] in enriched_map:
            record.update(enriched_map[record["domain"]])

    output_path = output or auto_csv_name(primary_seed)
    out.status(f"Step 7/8: Exporting to {output_path}...")

    if str(output_path).endswith(".json"):
        from discolike.exporters.json_export import export_json

        export_json({"records": all_records, "count": len(all_records)}, output_path)
    else:
        export_csv(all_records, output_path, seed_domain=primary_seed)

    out.success(f"  Saved {len(all_records)} records to {output_path}")

    # Step 8: Save exclusion list
    if save_exclusion:
        domains_to_save = [r["domain"] for r in all_records if r.get("domain")]
        exclusion_name = (
            f"{primary_seed} - Discovery - {datetime.date.today().isoformat()}"
        )
        out.status(
            f"Step 8/8: Saving exclusion list ({len(domains_to_save)} domains)..."
        )
        client.save_exclusion(exclusion_name, domains_to_save)
        out.success(f"  Saved exclusion list: {exclusion_name}")
    else:
        out.status("Step 8/8: Skipping exclusion save (use --save-exclusion to enable)")

    _show_running_cost(out, client)

    # Final summary
    out.success("Workflow complete!")
    out.status(f"  Records: {len(all_records)}")
    out.status(f"  Enriched: {len(enriched_records)}")
    out.status(f"  Output: {output_path}")
    out.status(f"  Total cost: ${client.cost_tracker.session_total:.2f}")


@workflow.command("enrich-list")
@click.option(
    "--input",
    "input_file",
    required=True,
    type=click.Path(exists=True),
    help="Input file with domains",
)
@click.option("--output", "-o", required=True, type=click.Path(), help="Output file path")
@click.option(
    "--fields",
    "enrich_fields",
    type=str,
    default="profile,score,growth",
    help="Enrichment types: profile,score,growth",
)
@handle_errors
@click.pass_context
def workflow_enrich_list(
    ctx: click.Context,
    input_file: str,
    output: str,
    enrich_fields: str,
) -> None:
    """Enrich a list of domains with profiles, scores, and growth data."""
    from discolike.errors import ValidationError

    client = get_client(ctx)
    cli_ctx = _get_context(ctx)
    out = cli_ctx.output

    # Parse enrichment types
    requested = {f.strip().lower() for f in enrich_fields.split(",")}
    valid_types = {"profile", "score", "growth"}
    invalid = requested - valid_types
    if invalid:
        raise ValidationError(
            f"Invalid enrichment types: {', '.join(sorted(invalid))}. "
            f"Valid: {', '.join(sorted(valid_types))}"
        )

    # Read domains
    domains: list[str] = []
    with open(input_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                domains.append(line.split(",")[0].strip())

    if not domains:
        raise ValidationError("No domains found in input file.")

    out.status(f"Enriching {len(domains)} domains with: {', '.join(sorted(requested))}")

    results: list[dict[str, Any]] = []
    with Progress() as progress:
        task = progress.add_task("Enriching...", total=len(domains))

        for domain in domains:
            record: dict[str, Any] = {"domain": domain}

            if "profile" in requested:
                profile = client.business_profile(domain)
                record.update(profile.model_dump(mode="json"))

            if "score" in requested:
                score_result = client.score(domain)
                score_data = score_result.model_dump(mode="json")
                record["digital_footprint_score"] = score_data.get("score")
                record["score_parameters"] = score_data.get("parameters")

            if "growth" in requested:
                growth_result = client.growth(domain)
                growth_data = growth_result.model_dump(mode="json")
                record["score_growth_3m"] = growth_data.get("score_growth_3m")
                record["subdomain_growth_3m"] = growth_data.get("subdomain_growth_3m")

            results.append(record)
            progress.update(task, advance=1)

    # Export
    output_path = Path(output)
    if output_path.suffix.lower() == ".csv":
        export_csv(results, output_path)
    else:
        from discolike.exporters.json_export import export_json

        export_json({"records": results, "count": len(results)}, output_path)

    out.success(f"Enriched {len(results)} domains -> {output_path}")
    out.status(f"Total cost: ${client.cost_tracker.session_total:.2f}")


def _show_running_cost(out: Any, client: Any) -> None:
    """Show running cost total."""
    total = client.cost_tracker.session_total
    out.status(f"  Running cost: ${total:.2f}")
