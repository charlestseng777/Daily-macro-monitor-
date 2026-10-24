"""Stooq daily CSV downloads: global bond yields, FX, indices."""

from __future__ import annotations

import io

import pandas as pd

from .base import HttpClient, SourceError, clean_series

URL = "https://stooq.com/q/d/l/"


def parse_csv(text: str, symbol: str) -> pd.Series:
    if not text.lstrip().lower().startswith("date"):
        # Stooq answers unknown symbols / quota limits with a plain message.
        raise SourceError(f"Stooq {symbol}: {text.strip()[:80] or 'empty response'}")
    frame = pd.read_csv(io.StringIO(text))
    if "Close" not in frame.columns:
        raise SourceError(f"Stooq {symbol}: no Close column")
    return clean_series(dict(zip(frame["Date"], pd.to_numeric(frame["Close"], errors="coerce"))), symbol)


def fetch(http: HttpClient, code: str, start: str) -> pd.Series:
    text = http.get_text(URL, params={"s": code, "i": "d", "d1": start.replace("-", "")})
    return parse_csv(text, code)
