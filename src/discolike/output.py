"""Output management -- Rich tables, JSON, CSV with dual-mode support."""

from __future__ import annotations

import csv
import io
import json
import sys
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import click
from pydantic import BaseModel
from rich.console import Console
from rich.table import Table

from discolike.types import CostBreakdown, CostMeta


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal values."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


class OutputManager:
    """Manages CLI output in table, JSON, or CSV mode."""

    def __init__(
        self,
        json_output: bool = False,
        csv_output: bool = False,
        fields: list[str] | None = None,
        quiet: bool = False,
    ) -> None:
        self.json_output = json_output
        self.csv_output = csv_output
        self.fields = fields
        self.quiet = quiet
        self._console = Console()
        self._stderr = Console(stderr=True)

    @property
    def is_tty(self) -> bool:
        return sys.stdout.isatty() and not self.json_output and not self.csv_output

    def render(
        self,
        data: Any,
        title: str = "",
        columns: list[str] | None = None,
        cost: CostBreakdown | None = None,
        cached: bool = False,
    ) -> None:
        """Render data in the appropriate format."""
        if self.json_output or not sys.stdout.isatty():
            self._render_json(data, cost=cost, cached=cached)
        elif self.csv_output:
            self._render_csv(data, columns=columns)
        else:
            self._render_table(data, title=title, columns=columns, cost=cost, cached=cached)

    def _render_json(
        self,
        data: Any,
        cost: CostBreakdown | None = None,
        cached: bool = False,
    ) -> None:
        """Output as JSON with _meta block.

        Uses model_dump() (Python mode) so Decimal values stay as Decimal
        objects and get serialized to floats by DecimalEncoder.
        """
        if isinstance(data, BaseModel):
            output = data.model_dump()
        elif isinstance(data, list) and data and isinstance(data[0], BaseModel):
            output = {
                "records": [item.model_dump() for item in data],
                "count": len(data),
            }
        elif isinstance(data, list):
            output = {"records": data, "count": len(data)}
        elif isinstance(data, dict):
            output = data
        else:
            output = {"result": data}

        if cost:
            meta = CostMeta(
                cost=cost,
                cached=cached,
                timestamp=datetime.now(UTC).isoformat(),
            )
            output["_meta"] = meta.model_dump()

        click_echo_json(output)

    def _render_table(
        self,
        data: Any,
        title: str = "",
        columns: list[str] | None = None,
        cost: CostBreakdown | None = None,
        cached: bool = False,
    ) -> None:
        """Output as Rich table."""
        records = self._extract_records(data)
        if not records:
            self._stderr.print("[dim]No results.[/dim]")
            return

        # Determine columns
        if self.fields:
            cols = self.fields
        elif columns:
            cols = columns
        else:
            cols = list(records[0].keys())

        table = Table(title=title or None, show_lines=False)
        for col in cols:
            table.add_column(col, overflow="ellipsis", max_width=60)

        for record in records:
            row = []
            for col in cols:
                val = record.get(col, "")
                if isinstance(val, list):
                    val = "; ".join(str(v) for v in val)
                elif isinstance(val, dict):
                    val = json.dumps(val, cls=DecimalEncoder)
                elif val is None:
                    val = ""
                else:
                    val = str(val)
                # Truncate long values for table display
                if len(val) > 80:
                    val = val[:77] + "..."
                row.append(val)
            table.add_row(*row)

        self._console.print(table)

        # Cost footer
        if cost:
            self._render_cost_footer(cost, cached)

    def _render_csv(self, data: Any, columns: list[str] | None = None) -> None:
        """Output as CSV to stdout."""
        records = self._extract_records(data)
        if not records:
            return

        cols = self.fields or columns or list(records[0].keys())
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=cols, extrasaction="ignore")
        writer.writeheader()

        for record in records:
            row: dict[str, Any] = {}
            for col in cols:
                val = record.get(col, "")
                if isinstance(val, list):
                    val = "; ".join(str(v) for v in val)
                elif isinstance(val, dict):
                    val = json.dumps(val, cls=DecimalEncoder)
                elif val is None:
                    val = ""
                row[col] = val
            writer.writerow(row)

        sys.stdout.write(output.getvalue())

    def _render_cost_footer(self, cost: CostBreakdown, cached: bool) -> None:
        """Render cost info in table footer on stderr."""
        parts = []
        if cached:
            parts.append("[dim]cached[/dim]")
        else:
            parts.append(f"${cost.total:.4f}")
            if cost.estimated:
                parts.append("[dim](estimated)[/dim]")
        parts.append(f"session: ${cost.session_total:.2f}")
        if cost.budget_remaining is not None:
            parts.append(f"remaining: ${cost.budget_remaining:.2f}")
        self._stderr.print(f"  Cost: {' | '.join(parts)}")

    def _extract_records(self, data: Any) -> list[dict[str, Any]]:
        """Extract list of dicts from various data shapes."""
        if isinstance(data, BaseModel):
            d = data.model_dump(mode="json")
            if "records" in d and isinstance(d["records"], list):
                return d["records"]
            return [d]
        if isinstance(data, list):
            if data and isinstance(data[0], BaseModel):
                return [item.model_dump(mode="json") for item in data]
            if data and isinstance(data[0], dict):
                return data
            return [{"value": item} for item in data]
        if isinstance(data, dict):
            if "records" in data and isinstance(data["records"], list):
                return data["records"]
            return [data]
        return [{"result": data}]

    def status(self, message: str) -> None:
        """Print a status message to stderr."""
        if not self.quiet:
            self._stderr.print(f"[dim]{message}[/dim]")

    def success(self, message: str) -> None:
        """Print a success message to stderr."""
        if not self.quiet:
            self._stderr.print(f"[green]{message}[/green]")

    def warning(self, message: str) -> None:
        """Print a warning to stderr."""
        self._stderr.print(f"[yellow]Warning: {message}[/yellow]")

    def error(self, message: str) -> None:
        """Print an error to stderr."""
        self._stderr.print(f"[red]Error: {message}[/red]")


def click_echo_json(data: Any) -> None:
    """Echo JSON to stdout using our Decimal-aware encoder."""
    click.echo(json.dumps(data, indent=2, cls=DecimalEncoder))
