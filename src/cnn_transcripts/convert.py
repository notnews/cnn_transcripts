"""Build the Parquet deliverable from JSONL checkpoints and the legacy CSVs.

The eight ``cnn-N.csv`` files on Dataverse were written by three generations
of scraper with the columns ``url, channel.name, program.name, uid, duration,
year, month, date, time, timezone, path, wordcount, subhead, text``.
``channel.name`` was a constant and ``duration`` was never filled, so both
are dropped. Everything else maps onto the schema below.
"""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from datetime import date
from typing import TYPE_CHECKING, Any

import pyarrow as pa
import pyarrow.parquet as pq

if TYPE_CHECKING:
    from pathlib import Path

# Explicit so a malformed row fails here rather than being inferred as a
# string column downstream.
SCHEMA = pa.schema(
    [
        pa.field("url", pa.string(), nullable=False),
        pa.field("program", pa.string()),
        pa.field("subhead", pa.string()),
        pa.field("aired_date", pa.date32()),
        pa.field("aired_time", pa.string()),
        pa.field("timezone", pa.string()),
        pa.field("uid", pa.string()),
        pa.field("path", pa.string()),
        pa.field("wordcount", pa.int32()),
        pa.field("text", pa.string()),
        pa.field("source", pa.string(), nullable=False),
    ]
)

# Legacy CSVs were written on a laptop with the default field size limit,
# which some transcripts exceed on read.
csv.field_size_limit(sys.maxsize)


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _legacy_date(row: dict[str, str]) -> date | None:
    try:
        return date(int(row["year"]), int(row["month"]), int(row["date"]))
    except (KeyError, TypeError, ValueError):
        return None


def _legacy_time(value: str | None) -> str | None:
    value = _blank_to_none(value)
    if value is None:
        return None
    hour, _, minute = value.partition(":")
    try:
        return f"{int(hour):02d}:{int(minute):02d}"
    except ValueError:
        return None


def _wordcount(text: str | None, existing: str | None) -> int | None:
    if existing and existing.strip().isdigit():
        return int(existing)
    return len(text.split()) if text else 0


def rows_from_csv(path: Path) -> list[dict[str, Any]]:
    """Read one legacy ``cnn-N.csv`` into records matching :data:`SCHEMA`."""
    records = []
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            text = _blank_to_none(row.get("text"))
            url = _blank_to_none(row.get("url"))
            if url is None:
                continue
            parts = url.rstrip("/").split("/")
            records.append(
                {
                    "url": url,
                    "program": _blank_to_none(row.get("program.name")),
                    "subhead": _blank_to_none(row.get("subhead")),
                    "aired_date": _legacy_date(row),
                    "aired_time": _legacy_time(row.get("time")),
                    "timezone": _blank_to_none(row.get("timezone")),
                    "uid": _blank_to_none(row.get("uid"))
                    or parts[-1].removesuffix(".html"),
                    "path": _blank_to_none(row.get("path")) or "/".join(parts[-2:]),
                    "wordcount": _wordcount(text, row.get("wordcount")),
                    "text": text,
                    "source": path.name,
                }
            )
    return records


def rows_from_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read a scraper checkpoint into records matching :data:`SCHEMA`."""
    records = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            aired = row.get("aired_date")
            records.append(
                {
                    "url": row["url"],
                    "program": row.get("program"),
                    "subhead": row.get("subhead"),
                    "aired_date": date.fromisoformat(aired) if aired else None,
                    "aired_time": row.get("aired_time"),
                    "timezone": row.get("timezone"),
                    "uid": row.get("uid"),
                    "path": row.get("path"),
                    "wordcount": row.get("wordcount"),
                    "text": row.get("text"),
                    "source": path.name,
                }
            )
    return records


def load_records(paths: list[Path]) -> tuple[list[dict[str, Any]], int]:
    """Read every input, in order, dropping repeats of a URL seen earlier.

    Args:
        paths: ``.csv`` (legacy) and ``.jsonl`` (new) files. Order matters:
            the first occurrence of a URL wins.

    Returns:
        The kept records and the number of duplicate URLs dropped.
    """
    seen: set[str] = set()
    kept: list[dict[str, Any]] = []
    dropped = 0
    for path in paths:
        reader = rows_from_csv if path.suffix == ".csv" else rows_from_jsonl
        for record in reader(path):
            if record["url"] in seen:
                dropped += 1
                continue
            seen.add(record["url"])
            kept.append(record)
    return kept, dropped


def write_parquet(records: list[dict[str, Any]], out: Path) -> pa.Table:
    """Write records to ``out`` under :data:`SCHEMA` and return the table."""
    table = pa.Table.from_pylist(records, schema=SCHEMA)
    out.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, out, compression="zstd", row_group_size=50_000)
    return table


def describe(table: pa.Table, dropped: int) -> str:
    """Human-readable summary: rows per source, duplicates, rows per year."""
    lines = [f"rows: {table.num_rows}  duplicates dropped: {dropped}", "per source:"]
    lines.extend(
        f"  {name}: {count}"
        for name, count in sorted(Counter(table.column("source").to_pylist()).items())
    )
    years = Counter(
        d.year if d else None for d in table.column("aired_date").to_pylist()
    )
    lines.append("per year:")
    lines.extend(
        f"  {year or 'missing'}: {count}"
        for year, count in sorted(years.items(), key=lambda kv: (kv[0] is None, kv[0]))
    )
    return "\n".join(lines)
