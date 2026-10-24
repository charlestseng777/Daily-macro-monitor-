"""Yahoo Finance chart API (daily closes). Unofficial and rate-limited, so it
sits behind official sources in every instrument's source list."""

from __future__ import annotations

import datetime as dt
import json

import pandas as pd

from .base import HttpClient, SourceError, clean_series

URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
MONTH_CODES = "FGHJKMNQUVXZ"


def parse_chart(text: str, symbol: str) -> pd.Series:
    payload = json.loads(text)
    chart = payload.get("chart", {})
    if chart.get("error") or not chart.get("result"):
        raise SourceError(f"Yahoo {symbol}: {chart.get('error') or 'empty result'}")
    result = chart["result"][0]
    stamps = result.get("timestamp") or []
    closes = (result.get("indicators", {}).get("quote") or [{}])[0].get("close") or []
    offset = int(result.get("meta", {}).get("gmtoffset", 0))
    values = {}
    for ts, close in zip(stamps, closes):
        if close is None:
            continue
        # Exchange-local calendar date, not UTC (Tokyo closes are 'yesterday' in UTC).
        values[dt.datetime.fromtimestamp(ts + offset, dt.UTC).date()] = float(close)
    return clean_series(values, symbol)


def fetch(http: HttpClient, code: str, start: str) -> pd.Series:
    p1 = int(dt.datetime.fromisoformat(start).replace(tzinfo=dt.UTC).timestamp())
    p2 = int(dt.datetime.now(dt.UTC).timestamp()) + 86400
    text = http.get_text(URL.format(symbol=code), params={
        "period1": p1, "period2": p2, "interval": "1d", "includePrePost": "false", "events": ""})
    s = parse_chart(text, code)
    if len(s) < 20:
        # Some exchanges (e.g. Shanghai) answer a period query with one bar;
        # a named range returns the full daily history.
        s = parse_chart(http.get_text(URL.format(symbol=code), params={"range": "10y", "interval": "1d"}), code)
        s = s[s.index >= pd.Timestamp(start)]
    return s


def fed_funds_contract(year: int, month: int) -> str:
    """CBOT 30-day fed funds future ticker on Yahoo, e.g. ZQZ26.CBT."""
    return f"ZQ{MONTH_CODES[month - 1]}{year % 100:02d}.CBT"


def last_close(http: HttpClient, symbol: str) -> float | None:
    start = (dt.date.today() - dt.timedelta(days=14)).isoformat()
    try:
        s = fetch(http, symbol, start)
    except SourceError:
        return None
    return float(s.iloc[-1]) if len(s) else None
