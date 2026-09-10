## CNN Transcripts 2000--2025

[![CI](https://github.com/notnews/cnn_transcripts/actions/workflows/ci.yml/badge.svg)](https://github.com/notnews/cnn_transcripts/actions/workflows/ci.yml)
[![Data: Dataverse](https://img.shields.io/badge/data-10.7910%2FDVN%2FISDPJU-blue)](https://doi.org/10.7910/DVN/ISDPJU)
[![License: MIT](https://img.shields.io/badge/code-MIT-green)](LICENSE)

Every transcript CNN published at [transcripts.cnn.com](https://transcripts.cnn.com/) from 2000-01-01 to 2025-03-15: 336,902 show segments, each with program, subhead, air date and time, and the full text. This repository holds the scraper that produced the corpus and the record of how each era of CNN's site was parsed. The corpus itself lives on Harvard Dataverse at [doi:10.7910/DVN/ISDPJU](https://doi.org/10.7910/DVN/ISDPJU); for copyright reasons access is restricted to research use.

### Data

The Dataverse dataset holds eight CSV files, one per scraping run:

| File | Aired | Segments |
|---|---|---|
| `cnn-1.csv` | 2000-01-01 to 2000-04-20 | 7,017 |
| `cnn-2.csv` | 2000-04-21 to 2001-04-03 | 21,381 |
| `cnn-3.csv` | 2001-04-04 to 2002-08-06 | 35,269 |
| `cnn-4.csv` | 2002-08-07 to 2002-09-16 | 2,343 |
| `cnn-5.csv` | 2002-09-17 to 2012-05-18 | 101,336 |
| `cnn-6.csv` | 2012-05-19 to 2014-06-17 | 23,536 |
| `cnn-7.csv` | 2014-06-18 to 2022-02-05 | 102,458 |
| `cnn-8.csv` | 2022-02-01 to 2025-03-15 | 43,562 |

`cnn-7` and `cnn-8` overlap by five days; `cnn-transcripts to-parquet` (below) drops the repeats by URL. Two segments from July 2024 were lost to connection errors in the 2025 run; the scraper now retries and reports such URLs so they can be re-run.

**Columns.** The CSVs use the original scraper's columns. The Parquet build renames them and drops two that carried no information:

| CSV | Parquet | Notes |
|---|---|---|
| `url` | `url` | As fetched. Old form `.../TRANSCRIPTS/0507/12/lkl.01.html`, new form `.../show/acd/date/2025-03-14/segment/01`. |
| `program.name` | `program` | Show name as printed, e.g. `CNN LARRY KING LIVE`. |
| `subhead` | `subhead` | Segment title. From 2024 CNN appends the slot ("Aired 8-9p ET"); the scraper strips it. |
| `year`, `month`, `date` | `aired_date` | `date32`. |
| `time` | `aired_time` | `HH:MM`, 24-hour, as printed. |
| `timezone` | `timezone` | Almost always `ET`. |
| `uid` | `uid` | `<show code>.<segment>`, e.g. `lkl.01`, `acd.01`. |
| `path` | `path` | URL path after the host, e.g. `0507/12/lkl.01.html`. The CSVs kept only the last two segments. |
| `wordcount` | `wordcount` | `int32`, recomputed from `text` where the CSV left it blank. |
| `text` | `text` | Paragraphs joined by newlines. The "THIS IS A RUSH TRANSCRIPT" and "TO ORDER A VIDEO" notices are removed. |
| `channel.name` | dropped | Constant. |
| `duration` | dropped | Never populated. |
| | `source` | Input file the row came from. |

### Coverage

CNN began posting transcripts online around 1999-10-01, and its own index for late 1999 still exists at [edition.cnn.com/TRANSCRIPTS/1999.10.01.html](http://edition.cnn.com/TRANSCRIPTS/1999.10.01.html), but every transcript it links to returns "Page not found", so the corpus starts on 2000-01-01.

The Internet Archive does not extend this. Its CDX index holds only two distinct CNN transcript URLs captured before 2000 (`/TRANSCRIPTS/9812/16/blair/` and `/TRANSCRIPTS/9904/28/pin.00.html`), and the eight 1999 daily index pages it captured are mostly redirects. Archive Team's [CNN Transcript Collection 2000-2012](https://archive.org/details/cnn-transcripts-2000-2012) (1 GB) overlaps the range already covered here and could serve as a completeness check, not an extension. Pre-2000 CNN transcripts exist in full text only in Nexis Uni, which requires institutional access.

### How the data were collected

The scraper visits the daily index `https://transcripts.cnn.com/TRANSCRIPTS/YYYY.MM.DD.html`, follows every transcript link, and parses the page. CNN changed the markup twice, so the parser dispatches on what it finds:

| Aired | Index page | Transcript page |
|---|---|---|
| 2000-01-01 to 2001-04-03 | `<LI><A HREF>` list | `<h2>` program, `<h3>` subhead, bare "Aired ..." text, `<p>` paragraphs |
| 2001-04-04 to 2002-09-16 | `<LI><A HREF>` list | `<h2>` program, `<h4>` subhead, body in a following `<table>` split by `<br>` |
| 2002-09-17 onward | `div.cnnTransDate` + `div.cnnSectBulletItems` | `p.cnnTransStoryHead`, `p.cnnTransSubHead`, `p.cnnBodyText` (first is the "Aired" line) |

From 2024 the links changed to `/show/<code>/date/<YYYY-MM-DD>/segment/<NN>`; the page markup did not. Each layout has a fixture in `tests/fixtures/` taken from the Wayback Machine (see `tests/fixtures/SOURCES.md`) and a test asserting the parsed fields.

The scripts that produced the eight CSVs are preserved at commit [`26aa2e1`](https://github.com/notnews/cnn_transcripts/tree/26aa2e1c1cfa5f96a75f1f567a2b15394c0e671c/scripts). They were rewritten in 2026 into the package here, fixing bugs that affected the CSVs at the margins: a two-digit-hour regex that dropped the air time on single-digit hours, variables that leaked a previous page's date into a page with no "Aired" line, and body extraction that kept only the last paragraph in some layouts.

### Usage

```bash
uv sync --group dev

# Scrape a date range into an append-only JSONL checkpoint. Re-running the same
# command skips URLs already in the file, so a crash costs nothing.
uv run cnn-transcripts scrape --start 2025-03-16 --end 2025-03-31 --out data/cnn.jsonl

# Combine legacy CSVs and JSONL into one typed Parquet file, deduplicated by URL.
uv run cnn-transcripts to-parquet data/cnn-*.csv data/cnn.jsonl --out data/cnn_transcripts.parquet

# Add a file to the Dataverse dataset (needs DATAVERSE_API_TOKEN in the environment).
uv run cnn-transcripts upload data/cnn_transcripts.parquet
```

`scrape` defaults to 60 requests per minute, three retries, and a 30-second timeout. It exits non-zero and lists the failed URLs if any transcript could not be fetched.

Development: `uv run ruff check . && uv run ruff format --check . && uv run pytest`, or `uv run pre-commit install` once.

### Citation

See [CITATION.cff](CITATION.cff). Please cite the Dataverse DOI for the data.

### License

Code is MIT. The transcripts are CNN's; the Dataverse copy is restricted to research use.

## 🔗 Adjacent Repositories

- [notnews/fox_news_transcripts](https://github.com/notnews/fox_news_transcripts) — Fox News Transcripts 2003--2025
- [notnews/msnbc_transcripts](https://github.com/notnews/msnbc_transcripts) — MSNBC Transcripts: 2003--2022
- [notnews/archive_news_cc](https://github.com/notnews/archive_news_cc) — Closed Caption Transcripts of News Videos from archive.org 2014--2023
- [notnews/stanford_tv_news](https://github.com/notnews/stanford_tv_news) — Stanford Cable TV News Dataset
- [notnews/nbc_transcripts](https://github.com/notnews/nbc_transcripts) — NBC transcripts 2011--2014
