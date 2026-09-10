from datetime import date

import pytest

from cnn_transcripts.parsers import (
    ParseError,
    parse_aired,
    parse_index,
    parse_transcript,
)

RUSH = "THIS IS A RUSH TRANSCRIPT"

# One case per markup era. Expected values were read off the raw pages.
TRANSCRIPT_CASES = [
    (
        "transcript_2000_h3.html",
        "http://www.cnn.com/TRANSCRIPTS/0001/05/lkl.00.html",
        "Larry King Live",
        "Should Elian Gonzalez Return to His Father in Cuba?",
        date(2000, 1, 5),
        "21:00",
        "lkl.00",
        "0001/05/lkl.00.html",
        "LARRY KING, HOST: Tonight, U.S. immigration officials",
    ),
    (
        "transcript_2001_h4.html",
        "http://www.cnn.com/TRANSCRIPTS/0106/12/lkl.00.html",
        "CNN LARRY KING LIVE",
        "Paul McCartney Discusses 'Blackbird Singing'",
        date(2001, 6, 12),
        "21:00",
        "lkl.00",
        "0106/12/lkl.00.html",
        "LARRY KING, HOST: What a pleasure",
    ),
    (
        "transcript_2005_classed.html",
        "http://transcripts.cnn.com/TRANSCRIPTS/0507/12/lkl.01.html",
        "CNN LARRY KING LIVE",
        "White House Pressured Over Karl Rove's Role in Releasing CIA Operative's "
        "Name; Search for Natalee Holloway Continues",
        date(2005, 7, 12),
        "21:00",
        "lkl.01",
        "0507/12/lkl.01.html",
        "LARRY KING, HOST: Tonight, still no sign of Natalee Holloway",
    ),
    (
        "transcript_2013_classed.html",
        "http://transcripts.cnn.com/TRANSCRIPTS/1301/15/acd.01.html",
        "ANDERSON COOPER 360 DEGREES",
        "Lance's Lies and His Strong-Arm Machine; Growing Sandy Hook Conspiracies",
        date(2013, 1, 15),
        "20:00",
        "acd.01",
        "1301/15/acd.01.html",
        "ANDERSON COOPER, CNN ANCHOR: Erin, thanks.\nGood evening, everyone.",
    ),
    (
        "transcript_2025_classed.html",
        "https://transcripts.cnn.com/show/acd/date/2025-03-14/segment/01",
        "Anderson Cooper 360 Degrees",
        None,  # long; checked separately for the stripped "Aired 8-9p ET" tail
        date(2025, 3, 14),
        "20:00",
        "acd.01",
        "show/acd/date/2025-03-14/segment/01",
        "EV WILLIAMS, TWITTER, CO-FOUNDER AND CEO:",
    ),
]


@pytest.mark.parametrize(
    ("name", "url", "program", "subhead", "aired", "time", "uid", "path", "start"),
    TRANSCRIPT_CASES,
    ids=[c[0] for c in TRANSCRIPT_CASES],
)
def test_parse_transcript_each_era(
    fixture_html, name, url, program, subhead, aired, time, uid, path, start
):
    t = parse_transcript(fixture_html(name), url)
    assert t.program == program
    if subhead is not None:
        assert t.subhead == subhead
    assert (t.aired_date, t.aired_time, t.timezone) == (aired, time, "ET")
    assert (t.uid, t.path) == (uid, path)
    assert t.text.startswith(start)
    assert RUSH not in t.text
    assert "Aired " not in t.text
    assert t.wordcount == len(t.text.split()) > 50


def test_subhead_drops_trailing_air_slot(fixture_html):
    t = parse_transcript(
        fixture_html("transcript_2025_classed.html"),
        "https://transcripts.cnn.com/show/acd/date/2025-03-14/segment/01",
    )
    assert t.subhead.startswith("Trump Lashes Out At Political Enemies")
    assert t.subhead.endswith("Burst Into Flames At Denver Airport")
    assert "Aired" not in t.subhead


def test_legacy_body_excludes_page_furniture(fixture_html):
    t = parse_transcript(
        fixture_html("transcript_2000_h3.html"),
        "http://www.cnn.com/TRANSCRIPTS/0001/05/lkl.00.html",
    )
    assert "TO ORDER A VIDEO" not in t.text
    assert "furniture" not in t.text
    assert "Search" not in t.text.split("\n")[-1]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Aired January 5, 2000 - 9:00 p.m. ET", (date(2000, 1, 5), "21:00", "ET")),
        ("Aired June 12, 2001 - 21:00 \xa0 ET", (date(2001, 6, 12), "21:00", "ET")),
        ("Aired March 14, 2025 - 20:00 &nbsp; ET", (date(2025, 3, 14), "20:00", "ET")),
        ("Aired  October 3, 2004 - 7:00 a.m. ET", (date(2004, 10, 3), "07:00", "ET")),
        ("Aired 8-9p ET", (None, None, None)),
        ("no air line at all", (None, None, None)),
    ],
)
def test_parse_aired(text, expected):
    a = parse_aired(text.replace("&nbsp;", "\xa0"))
    assert (a.date, a.time, a.timezone) == expected


def test_missing_aired_line_yields_none_not_previous_value():
    html = (
        '<p class="cnnTransStoryHead">Show</p><p class="cnnTransSubHead">Sub</p>'
        '<p class="cnnBodyText">HOST: hello there everyone.</p>'
    )
    t = parse_transcript(
        html, "http://transcripts.cnn.com/TRANSCRIPTS/0507/12/x.01.html"
    )
    assert (t.aired_date, t.aired_time, t.timezone) == (None, None, None)
    assert t.text == "HOST: hello there everyone."


def test_unknown_layout_raises():
    with pytest.raises(ParseError):
        parse_transcript("<html><body><p>nothing</p></body></html>", "http://x/y.html")


@pytest.mark.parametrize(
    ("name", "base", "count", "first", "last"),
    [
        (
            "index_2000.html",
            "http://www.cnn.com/TRANSCRIPTS/2000.01.03.html",
            69,
            "http://www.cnn.com/TRANSCRIPTS/0001/03/mlld.00.html",
            "http://www.cnn.com/TRANSCRIPTS/0001/03/i_se.00.html",
        ),
        (
            "index_2005.html",
            "http://transcripts.cnn.com/TRANSCRIPTS/2005.07.12.html",
            30,
            "http://transcripts.cnn.com/TRANSCRIPTS/0507/12/ltm.01.html",
            "http://transcripts.cnn.com/TRANSCRIPTS/0507/12/ywt.01.html",
        ),
        (
            "index_2025.html",
            "https://transcripts.cnn.com/TRANSCRIPTS/2025.03.14.html",
            43,
            "https://transcripts.cnn.com/show/acd/date/2025-03-14/segment/01",
            "https://transcripts.cnn.com/show/skc/date/2025-03-14/segment/01",
        ),
    ],
)
def test_parse_index_each_era(fixture_html, name, base, count, first, last):
    urls = parse_index(fixture_html(name), base)
    assert len(urls) == count
    assert len(set(urls)) == count
    assert urls[0] == first
    assert urls[-1] == last
    assert all(u.startswith("http") for u in urls)
