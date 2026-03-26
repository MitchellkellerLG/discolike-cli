"""JSON export for DiscoLike results."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from discolike.output import DecimalEncoder


def export_json(
    data: Any,
    output_path: Path | str,
    indent: int = 2,
) -> Path:
    """Export data to JSON file."""
    output_path = Path(output_path)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, cls=DecimalEncoder)
    return output_path


def export_jsonl(
    records: list[dict[str, Any]],
    output_path: Path | str,
) -> Path:
    """Export records as JSONL (one JSON object per line)."""
    output_path = Path(output_path)
    with open(output_path, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, cls=DecimalEncoder) + "\n")
    return output_path
