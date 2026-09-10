"""Walk CNN's daily transcript index and append each segment to a JSONL file.

JSONL is the checkpoint format because it is append-only: a crash or a
Ctrl-C loses at most the row being written, and the next run resumes by
reading the URLs already present. Parquet cannot do that; its footer is
written on close. Convert with :mod:`cnn_transcripts.convert` when done.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING

import scrapelib

from cnn_transcripts.parsers import ParseError, parse_index, parse_transcript

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

log = logging.getLogger(__name__)

INDEX_URL = "https://transcripts.cnn.com/TRANSCRIPTS/{d:%Y.%m.%d}.html"


@dataclass(slots=True)
class ScrapeSummary:
    """Counts reported at the end of a run."""

    days: int = 0
    urls_seen: int = 0
    written: int = 0
    skipped: int = 0
    failed: list[str] = field(default_factory=list)


def days_between(start: date, end: date) -> Iterator[date]:
    """Yield every date from ``start`` to ``end`` inclusive."""
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def load_seen_urls(path: Path) -> set[str]:
    """Return the URLs already present in a JSONL checkpoint, if it exists."""
    if not path.exists():
        return set()
    with path.open(encoding="utf-8") as handle:
        return {json.loads(line)["url"] for line in handle if line.strip()}


def make_session(
    requests_per_minute: int, retries: int, timeout: float
) -> scrapelib.Scraper:
    """Build a rate-limited, retrying HTTP session.

    Args:
        requests_per_minute: Politeness cap; CNN has tolerated 60.
        retries: Retries per request on connection errors and 5xx responses.
        timeout: Seconds to wait per request. The 2025 run used none and lost
            two segments to a hung socket.

    Returns:
        A configured scrapelib session (a ``requests.Session`` subclass).
    """
    session = scrapelib.Scraper(
        requests_per_minute=requests_per_minute,
        retry_attempts=retries,
        retry_wait_seconds=10,
    )
    session.timeout = timeout
    session.headers["User-Agent"] = (
        "cnn-transcripts (https://github.com/notnews/cnn_transcripts)"
    )
    return session


def scrape(
    start: date,
    end: date,
    out: Path,
    *,
    requests_per_minute: int = 60,
    retries: int = 3,
    timeout: float = 30.0,
    session: scrapelib.Scraper | None = None,
) -> ScrapeSummary:
    """Scrape every transcript aired from ``start`` to ``end`` into ``out``.

    Args:
        start: First index day to visit.
        end: Last index day to visit, inclusive.
        out: JSONL file to append to. URLs already in it are skipped.
        requests_per_minute: Passed to :func:`make_session`.
        retries: Passed to :func:`make_session`.
        timeout: Passed to :func:`make_session`.
        session: Injected session for tests; built from the options otherwise.

    Returns:
        Counts of what was done, including URLs that failed after retries so
        they can be re-run.
    """
    session = session or make_session(requests_per_minute, retries, timeout)
    seen = load_seen_urls(out)
    summary = ScrapeSummary()
    if seen:
        log.info("resuming: %d transcripts already in %s", len(seen), out)

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a", encoding="utf-8") as handle:
        for day in days_between(start, end):
            summary.days += 1
            index_url = INDEX_URL.format(d=day)
            try:
                urls = parse_index(session.get(index_url).text, index_url)
            except Exception:
                log.exception("index failed for %s", day)
                summary.failed.append(index_url)
                continue
            log.info("%s: %d transcripts", day, len(urls))
            for url in urls:
                summary.urls_seen += 1
                if url in seen:
                    summary.skipped += 1
                    continue
                try:
                    transcript = parse_transcript(
                        session.get(url).text, url, datetime.now(UTC)
                    )
                except (scrapelib.HTTPError, ParseError, OSError):
                    log.exception("transcript failed: %s", url)
                    summary.failed.append(url)
                    continue
                handle.write(json.dumps(transcript.to_record(), ensure_ascii=False))
                handle.write("\n")
                handle.flush()
                seen.add(url)
                summary.written += 1
    log.info(
        "done: %d days, %d urls, %d written, %d skipped, %d failed",
        summary.days,
        summary.urls_seen,
        summary.written,
        summary.skipped,
        len(summary.failed),
    )
    for url in summary.failed:
        log.warning("failed: %s", url)
    return summary
