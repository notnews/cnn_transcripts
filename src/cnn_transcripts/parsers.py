"""HTML parsers for CNN's transcript pages, covering every layout since 2000.

CNN changed the transcript markup twice and the daily index markup twice. The
parsers dispatch on the markup they find rather than on the date, so a caller
never has to know which era a page belongs to.

Transcript page layouts:

* 2000-01-01 to 2001-04-03: ``<h2>`` program, ``<h3>`` subhead, a bare
  "Aired ..." text node, then ``<p>`` paragraphs.
* 2001-04-04 to 2002-09-16: ``<h2>`` program, ``<h4>`` subhead, "Aired ..."
  text node, body in a following ``<table>`` separated by ``<br>``.
* 2002-09-17 onward: ``p.cnnTransStoryHead``, ``p.cnnTransSubHead`` and
  ``p.cnnBodyText`` paragraphs, the first of which is the "Aired ..." line.

Daily index layouts:

* until 2002: ``<LI><A HREF="http://www.cnn.com/TRANSCRIPTS/0001/03/lkl.00.html">``
* 2002 onward: ``div.cnnTransDate`` followed by ``div.cnnSectBulletItems`` of
  links; from 2024 the hrefs look like ``/show/acd/date/2025-03-14/segment/01``.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from typing import Any
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup, Comment, NavigableString, Tag
from dateutil import parser as dateparser

TRANSCRIPT_HREF = re.compile(
    r"/TRANSCRIPTS/\d{4}/\d{2}/[^/\s\"']+\.html$"
    r"|/show/[^/\s]+/date/\d{4}-\d{2}-\d{2}/segment/\d+$",
    re.IGNORECASE,
)

# "Aired January 5, 2000 - 9:00 p.m. ET" / "Aired July 12, 2005 - 21:00   ET".
# The hour may be one or two digits; the old scripts required two and silently
# dropped the date on single-digit hours.
AIRED = re.compile(
    r"Aired\s+(?P<date>[A-Za-z]+\.?\s+\d{1,2},\s+\d{4})"
    r"\s*-\s*(?P<time>\d{1,2}:\d{2})\s*(?P<ampm>[ap]\.?m\.?)?"
    r"\s*(?P<tz>[A-Z]{2,4})?",
    re.IGNORECASE,
)

RUSH_NOTICE = "THIS IS A RUSH TRANSCRIPT"
ORDER_NOTICE = "TO ORDER A VIDEO OF THIS TRANSCRIPT"


@dataclass(slots=True)
class Aired:
    """When a segment aired, as printed on the page."""

    date: date | None = None
    time: str | None = None
    timezone: str | None = None


@dataclass(slots=True)
class Transcript:
    """One transcript segment, the unit of the corpus."""

    url: str
    program: str | None
    subhead: str | None
    aired_date: date | None
    aired_time: str | None
    timezone: str | None
    uid: str
    path: str
    wordcount: int
    text: str
    scraped_at: datetime

    def to_record(self) -> dict[str, Any]:
        """Return a JSON-serialisable dict with ISO-formatted dates."""
        record = asdict(self)
        record["aired_date"] = self.aired_date.isoformat() if self.aired_date else None
        record["scraped_at"] = self.scraped_at.isoformat()
        return record


class ParseError(ValueError):
    """Raised when a page has none of the known transcript layouts."""


def normalize_space(text: str) -> str:
    """Collapse runs of whitespace, including non-breaking spaces, to one space."""
    return " ".join(text.split())


def parse_aired(text: str) -> Aired:
    """Extract the air date, time and timezone from an "Aired ..." line.

    Args:
        text: Any text containing an "Aired <Month> <day>, <year> - <time>" run.

    Returns:
        The parsed components. Every field is ``None`` when the text has no
        recognisable "Aired" line, so a caller can never inherit a previous
        page's date.
    """
    match = AIRED.search(normalize_space(text))
    if not match:
        return Aired()
    when = f"{match['date']} {match['time']} {match['ampm'] or ''}".strip()
    try:
        parsed = dateparser.parse(when)
    except (ValueError, OverflowError):
        return Aired()
    tz = match["tz"].upper() if match["tz"] else None
    return Aired(parsed.date(), parsed.strftime("%H:%M"), tz)


def parse_index(html: str, base_url: str) -> list[str]:
    """Return the transcript URLs linked from a daily index page.

    Args:
        html: The index page markup, any era.
        base_url: URL the page was fetched from; relative links are resolved
            against it.

    Returns:
        Absolute URLs in page order, without duplicates.
    """
    soup = BeautifulSoup(html, "html.parser")
    seen: set[str] = set()
    urls: list[str] = []
    for anchor in soup.find_all("a", href=True):
        href = str(anchor["href"]).strip()
        if not TRANSCRIPT_HREF.search(href):
            continue
        url = urljoin(base_url, href)
        if url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def parse_transcript(
    html: str, url: str, scraped_at: datetime | None = None
) -> Transcript:
    """Parse one transcript page of any era.

    Args:
        html: The transcript page markup.
        url: Where it was fetched from; stored verbatim and used for ``uid``.
        scraped_at: Fetch time; defaults to now in UTC.

    Returns:
        The parsed transcript.

    Raises:
        ParseError: If the page matches none of the known layouts.
    """
    soup = BeautifulSoup(html, "html.parser")
    if soup.find("p", class_="cnnTransStoryHead"):
        program, subhead, aired, lines = _parse_classed(soup)
    elif soup.find("h2"):
        program, subhead, aired, lines = _parse_legacy(soup)
    else:
        raise ParseError(f"no known transcript layout at {url}")

    text = "\n".join(lines)
    parts = url.rstrip("/").split("/")
    return Transcript(
        url=url,
        program=program,
        subhead=subhead,
        aired_date=aired.date,
        aired_time=aired.time,
        timezone=aired.timezone,
        uid=_uid_from_url(parts),
        path=_path_from_url(url),
        wordcount=len(text.split()),
        text=text,
        scraped_at=scraped_at or datetime.now(UTC),
    )


def _uid_from_url(parts: list[str]) -> str:
    # Old: .../0507/12/lkl.01.html -> lkl.01
    # New: .../show/acd/date/2025-03-14/segment/01 -> acd.01
    if "segment" in parts:
        idx = parts.index("segment")
        return f"{parts[idx - 3]}.{parts[idx + 1]}"
    return parts[-1].removesuffix(".html")


def _path_from_url(url: str) -> str:
    """Return the URL path without host or the ``/TRANSCRIPTS/`` prefix.

    The old scripts stored only the last two segments (``12/lkl.01.html``),
    which lost the month; this keeps ``0507/12/lkl.01.html``.
    """
    path = urlsplit(url).path.lstrip("/")
    return re.sub(r"^TRANSCRIPTS/", "", path, flags=re.IGNORECASE)


# CNN appends the slot to the subhead: "...; Flight Burst Into Flames. Aired 8-9p ET"
TRAILING_SLOT = re.compile(r"\.?\s*Aired\s+[\d:apm.\-\s]+[A-Z]{2,4}\s*$", re.IGNORECASE)


def _is_boilerplate(line: str) -> bool:
    upper = line.upper()
    return (
        RUSH_NOTICE in upper
        or ORDER_NOTICE in upper
        or upper.startswith("AIRED ")
        or not line
    )


def _clean_lines(raw: str) -> list[str]:
    lines = (normalize_space(line) for line in raw.split("\n"))
    return [line for line in lines if not _is_boilerplate(line)]


def _parse_classed(
    soup: BeautifulSoup,
) -> tuple[str | None, str | None, Aired, list[str]]:
    head = soup.find("p", class_="cnnTransStoryHead")
    sub = soup.find("p", class_="cnnTransSubHead")
    aired = Aired()
    lines: list[str] = []
    for para in soup.find_all("p", class_="cnnBodyText"):
        text = para.get_text("\n")
        if aired.date is None:
            aired = parse_aired(text)
            if aired.date is not None:
                continue
        lines.extend(_clean_lines(text))
    return _text_or_none(head), _subhead(sub), aired, lines


def _parse_legacy(
    soup: BeautifulSoup,
) -> tuple[str | None, str | None, Aired, list[str]]:
    head = soup.find("h2")
    if not isinstance(head, Tag):  # pragma: no cover - caller checked
        raise ParseError("no <h2>")
    sub = head.find_next(["h3", "h4"])
    anchor = sub if isinstance(sub, Tag) else head
    # Body is whatever follows the subhead until the page furniture starts:
    # a bare "Aired ..." string, then <p>s (2000) or a <table> (2001-2002).
    chunks: list[str] = []
    for sibling in anchor.next_siblings:
        if isinstance(sibling, Tag):
            if sibling.name in {"div", "form", "script", "style"}:
                break
            chunks.append(sibling.get_text("\n"))
        elif isinstance(sibling, NavigableString) and not isinstance(sibling, Comment):
            chunks.append(str(sibling))
    body = "\n".join(chunks)
    return _text_or_none(head), _subhead(sub), parse_aired(body), _clean_lines(body)


def _text_or_none(tag: Tag | Any | None) -> str | None:
    if not isinstance(tag, Tag):
        return None
    text = normalize_space(tag.get_text())
    return text or None


def _subhead(tag: Tag | Any | None) -> str | None:
    text = _text_or_none(tag)
    if text is None:
        return None
    return TRAILING_SLOT.sub("", text).strip() or None
