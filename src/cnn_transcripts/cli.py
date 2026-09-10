"""Command-line entry point: ``cnn-transcripts scrape | to-parquet | upload``."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

from cnn_transcripts import convert, scrape, upload


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cnn-transcripts")
    sub = parser.add_subparsers(dest="command", required=True)

    s = sub.add_parser("scrape", help="append transcripts for a date range to JSONL")
    s.add_argument("--start", type=date.fromisoformat, required=True)
    s.add_argument("--end", type=date.fromisoformat, default=date.today())  # noqa: DTZ011
    s.add_argument("--out", type=Path, default=Path("data/cnn.jsonl"))
    s.add_argument("--log", type=Path, default=Path("data/scrape.log"))
    s.add_argument("--rpm", type=int, default=60, help="requests per minute")
    s.add_argument("--retries", type=int, default=3)
    s.add_argument("--timeout", type=float, default=30.0, help="seconds per request")

    p = sub.add_parser("to-parquet", help="combine CSV/JSONL inputs into one Parquet")
    p.add_argument("inputs", type=Path, nargs="+")
    p.add_argument("--out", type=Path, required=True)

    u = sub.add_parser("upload", help="add a file to the Dataverse dataset")
    u.add_argument("file", type=Path)
    u.add_argument("--doi", default=upload.DATASET_DOI)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the CLI and return an exit status."""
    args = _build_parser().parse_args(argv)
    if args.command == "scrape":
        args.log.parent.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(message)s",
            handlers=[logging.StreamHandler(), logging.FileHandler(args.log)],
        )
        summary = scrape.scrape(
            args.start,
            args.end,
            args.out,
            requests_per_minute=args.rpm,
            retries=args.retries,
            timeout=args.timeout,
        )
        return 1 if summary.failed else 0
    if args.command == "to-parquet":
        records, dropped = convert.load_records(args.inputs)
        table = convert.write_parquet(records, args.out)
        sys.stdout.write(convert.describe(table, dropped) + "\n")
        return 0
    if args.command == "upload":
        sys.stdout.write(upload.upload(args.file, args.doi) + "\n")
        return 0
    return 2  # pragma: no cover - argparse enforces the choices


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
