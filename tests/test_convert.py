import json
from datetime import date

import pyarrow.parquet as pq

from cnn_transcripts import convert

LEGACY_HEADER = (
    "url,channel.name,program.name,uid,duration,year,month,date,time,timezone,"
    "path,wordcount,subhead,text\n"
)


def write_legacy_csv(path, rows):
    path.write_text(LEGACY_HEADER + "".join(rows), encoding="utf-8")


def test_csv_and_jsonl_merge_into_typed_parquet(tmp_path):
    csv_path = tmp_path / "cnn-7.csv"
    write_legacy_csv(
        csv_path,
        [
            "http://transcripts.cnn.com/TRANSCRIPTS/2202/03/acd.01.html,CNN,AC360,"
            ',,2022,2,3,20:00,ET,03/acd.01.html,,Sub A,"hello world three"\n',
            "http://transcripts.cnn.com/TRANSCRIPTS/2202/03/acd.02.html,CNN,AC360,"
            ",,2022,2,3,9:00,ET,03/acd.02.html,7,Sub B,seven\n",
        ],
    )
    jsonl_path = tmp_path / "cnn.jsonl"
    rows = [
        {
            "url": "http://transcripts.cnn.com/TRANSCRIPTS/2202/03/acd.02.html",
            "program": "dup",
            "subhead": None,
            "aired_date": "2022-02-03",
            "aired_time": "21:00",
            "timezone": "ET",
            "uid": "acd.02",
            "path": "2202/03/acd.02.html",
            "wordcount": 1,
            "text": "dup",
            "scraped_at": "2026-01-01T00:00:00+00:00",
        },
        {
            "url": "https://transcripts.cnn.com/show/acd/date/2025-03-14/segment/01",
            "program": "AC360",
            "subhead": "New",
            "aired_date": None,
            "aired_time": None,
            "timezone": None,
            "uid": "acd.01",
            "path": "show/acd/date/2025-03-14/segment/01",
            "wordcount": 2,
            "text": "new row",
            "scraped_at": "2026-01-01T00:00:00+00:00",
        },
    ]
    jsonl_path.write_text("".join(json.dumps(r) + "\n" for r in rows))

    records, dropped = convert.load_records([csv_path, jsonl_path])
    assert dropped == 1  # the JSONL repeat of acd.02 loses to the CSV row
    assert [r["source"] for r in records] == ["cnn-7.csv", "cnn-7.csv", "cnn.jsonl"]

    out = tmp_path / "out.parquet"
    table = convert.write_parquet(records, out)
    assert table.schema.equals(convert.SCHEMA)
    back = pq.read_table(out)
    assert back.schema.equals(convert.SCHEMA)
    assert back.num_rows == 3

    first, second, third = back.to_pylist()
    assert first["aired_date"] == date(2022, 2, 3)
    assert first["aired_time"] == "20:00"
    assert first["wordcount"] == 3  # blank in CSV, recomputed from text
    assert first["uid"] == "acd.01"
    assert second["aired_time"] == "09:00"  # zero-padded
    assert second["wordcount"] == 7  # kept when present
    assert third["aired_date"] is None

    summary = convert.describe(back, dropped)
    assert "rows: 3" in summary
    assert "cnn-7.csv: 2" in summary
    assert "2022: 2" in summary
    assert "missing: 1" in summary
