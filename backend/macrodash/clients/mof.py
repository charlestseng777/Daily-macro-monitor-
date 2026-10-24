"""Japan Ministry of Finance JGB benchmark yields (constant maturity), CSV.
The history file runs to the end of the previous month; the current-month
file carries the rest. Codes are column names: '1Y', '2Y', '10Y', '30Y'..."""

from __future__ import annotations

import io

import pandas as pd

from .base import HttpClient, SourceError, clean_series

BASE = "https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/"
FILES = ("historical/jgbcme_all.csv", "jgbcme.csv")


def parse_csv(text: str) -> pd.DataFrame:
    lines = text.splitlines()
    header = next((i for i, l in enumerate(lines) if l.strip().lower().startswith("date")), None)
    if header is None:
        raise SourceError("MOF JGB CSV: no 'Date' header")
    frame = pd.read_csv(io.StringIO("\n".join(lines[header:])), na_values=["-", ""])
    frame.columns = [c.strip() for c in frame.columns]
    frame["Date"] = pd.to_datetime(frame["Date"], format="%Y/%m/%d", errors="coerce")
    return frame.dropna(subset=["Date"]).set_index("Date")


def fetch(http: HttpClient, code: str, start: str) -> pd.Series:
    parts = []
    for name in FILES:
        try:
            frame = parse_csv(http.get_text(BASE + name))
        except SourceError:
            continue
        if code in frame.columns:
            parts.append(pd.to_numeric(frame[code], errors="coerce"))
    if not parts:
        raise SourceError(f"MOF: no column {code}")
    s = clean_series(pd.concat(parts), code)
    return s[s.index >= pd.Timestamp(start)]
