"""CSV export for DiscoLike discovery results."""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path
from typing import Any

from discolike.constants import CSV_EXPORT_COLUMNS


def export_csv(
    records: list[dict[str, Any]],
    output_path: Path | str | None = None,
    seed_domain: str = "discovery",
    columns: list[str] | None = None,
) -> Path:
    """Export records to CSV file.

    Args:
        records: List of record dicts.
        output_path: Explicit output path. Auto-named if None.
        seed_domain: Used for auto-naming.
        columns: Column list. Defaults to CSV_EXPORT_COLUMNS.

    Returns:
        Path to the written CSV file.
    """
    cols = columns or CSV_EXPORT_COLUMNS
    if output_path is None:
        today = date.today().isoformat()
        seed_slug = seed_domain.replace(".", "-")
        output_path = Path(f"{seed_slug}-lookalikes-{today}.csv")
    else:
        output_path = Path(output_path)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            row: dict[str, Any] = {}
            for col in cols:
                val = record.get(col, "")
                if isinstance(val, list):
                    val = "; ".join(str(v) for v in val)
                elif isinstance(val, dict):
                    parts = []
                    for k, v in val.items():
                        if v:
                            parts.append(f"{k}: {v}")
                    val = "; ".join(parts)
                elif val is None:
                    val = ""
                row[col] = val
            writer.writerow(row)

    return output_path


def auto_csv_name(seed_domain: str) -> str:
    """Generate auto CSV filename."""
    today = date.today().isoformat()
    seed_slug = seed_domain.replace(".", "-")
    return f"{seed_slug}-lookalikes-{today}.csv"
