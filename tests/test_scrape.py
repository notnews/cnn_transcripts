import json
from datetime import date
from pathlib import Path

import pytest

from cnn_transcripts import scrape

FIXTURES = Path(__file__).parent / "fixtures"

INDEX = FIXTURES / "index_2025.html"
PAGE = FIXTURES / "transcript_2025_classed.html"


class FakeResponse:
    def __init__(self, text):
        self.text = text


class FakeSession:
    """Serves the 2025 index for any day and the same transcript for any URL."""

    def __init__(self, fail_on=None):
        self.calls = []
        self.fail_on = fail_on or set()

    def get(self, url):
        self.calls.append(url)
        if url in self.fail_on:
            raise OSError("boom")
        if url.endswith(".html") and "/TRANSCRIPTS/" in url:
            return FakeResponse(INDEX.read_text())
        return FakeResponse(PAGE.read_text())


def test_scrape_writes_jsonl_and_resumes(tmp_path):
    out = tmp_path / "cnn.jsonl"
    session = FakeSession()
    first = scrape.scrape(date(2025, 3, 14), date(2025, 3, 14), out, session=session)
    assert (first.days, first.written, first.skipped, first.failed) == (1, 43, 0, [])
    lines = out.read_text().splitlines()
    assert len(lines) == 43
    row = json.loads(lines[0])
    assert row["url"].endswith("/show/acd/date/2025-03-14/segment/01")
    assert row["aired_date"] == "2025-03-14"
    assert row["scraped_at"].endswith("+00:00")

    again = FakeSession()
    second = scrape.scrape(date(2025, 3, 14), date(2025, 3, 14), out, session=again)
    assert (second.written, second.skipped) == (0, 43)
    assert len(again.calls) == 1  # only the index page was fetched
    assert len(out.read_text().splitlines()) == 43


def test_failed_transcript_is_reported_and_skipped(tmp_path):
    out = tmp_path / "cnn.jsonl"
    bad = "https://transcripts.cnn.com/show/ampr/date/2025-03-14/segment/01"
    summary = scrape.scrape(
        date(2025, 3, 14), date(2025, 3, 14), out, session=FakeSession({bad})
    )
    assert summary.failed == [bad]
    assert summary.written == 42


@pytest.mark.parametrize(
    ("start", "end", "n"),
    [(date(2000, 1, 1), date(2000, 1, 1), 1), (date(2000, 2, 27), date(2000, 3, 1), 4)],
)
def test_days_between_is_inclusive(start, end, n):
    assert len(list(scrape.days_between(start, end))) == n
