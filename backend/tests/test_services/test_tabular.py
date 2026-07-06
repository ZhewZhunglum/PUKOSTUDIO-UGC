import pytest
from fastapi import HTTPException

from app.core.tabular import (
    normalize_format,
    parse_tabular,
    rows_to_csv_bytes,
    rows_to_xlsx_bytes,
    sheets_to_xlsx_bytes,
)


def test_parse_csv_lowercases_headers_and_trims():
    content = "Name,Email\n  Jane  , jane@example.com \n".encode("utf-8")
    rows = parse_tabular("people.csv", content)
    assert rows == [{"name": "Jane", "email": "jane@example.com"}]


def test_parse_csv_strips_bom():
    content = "﻿name,email\nJane,jane@example.com\n".encode("utf-8")
    rows = parse_tabular("bom.csv", content)
    assert rows[0]["name"] == "Jane"


def test_parse_rejects_unknown_extension():
    with pytest.raises(HTTPException) as exc:
        parse_tabular("data.txt", b"whatever")
    assert exc.value.status_code == 400


def test_xlsx_round_trip():
    headers = ["name", "email", "followers"]
    data = [["Jane Creator", "jane@example.com", 12000], ["Bob", "", 0]]
    blob = rows_to_xlsx_bytes(headers, data, sheet_title="Influencers")

    rows = parse_tabular("out.xlsx", blob)
    assert rows[0] == {"name": "Jane Creator", "email": "jane@example.com", "followers": "12000"}
    assert rows[1]["name"] == "Bob"
    assert rows[1]["email"] == ""


def test_parse_xlsx_skips_blank_rows():
    blob = rows_to_xlsx_bytes(["name"], [["A"], [None], ["B"]])
    rows = parse_tabular("x.xlsx", blob)
    assert [r["name"] for r in rows] == ["A", "B"]


def test_csv_bytes_have_bom_and_header():
    out = rows_to_csv_bytes(["a", "b"], [[1, 2]])
    assert out.startswith(b"\xef\xbb\xbf")  # utf-8-sig BOM for Excel
    text = out.decode("utf-8-sig")
    assert "a,b" in text and "1,2" in text


def test_sheets_to_xlsx_multiple_sheets_parse_first():
    blob = sheets_to_xlsx_bytes([
        ("Summary", ["metric", "value"], [["sent", 3]]),
        ("Daily", ["date", "sent"], [["2026-01-01", 3]]),
    ])
    # parse_tabular reads the active (first) sheet.
    rows = parse_tabular("report.xlsx", blob)
    assert rows[0] == {"metric": "sent", "value": "3"}


def test_normalize_format():
    assert normalize_format(None) == "csv"
    assert normalize_format("XLSX") == "xlsx"
    with pytest.raises(HTTPException):
        normalize_format("pdf")
