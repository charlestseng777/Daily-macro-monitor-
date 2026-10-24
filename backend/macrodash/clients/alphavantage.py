"""Alpha Vantage (needs ALPHAVANTAGE_API_KEY). Codes: 'FX:EURUSD' or 'EQ:SPY'."""

from __future__ import annotations

import json

import pandas as pd

from ..config import get_settings
from .base import HttpClient, SourceError, clean_series

URL = "https://www.alphavantage.co/query"


def parse(text: str, code: str) -> pd.Series:
    payload = json.loads(text)
    block = next((v for k, v in payload.items() if k.startswith("Time Series")), None)
    if not block:
        raise SourceError(f"AlphaVantage {code}: {payload.get('Note') or payload.get('Error Message') or 'no data'}")
    return clean_series({d: float(row["4. close"]) for d, row in block.items()}, code)


def fetch(http: HttpClient, code: str, start: str) -> pd.Series:
    key = get_settings().alphavantage_api_key
    if not key:
        raise SourceError("ALPHAVANTAGE_API_KEY not set")
    kind, symbol = code.split(":", 1)
    if kind == "FX":
        params = {"function": "FX_DAILY", "from_symbol": symbol[:3], "to_symbol": symbol[3:], "outputsize": "full"}
    else:
        params = {"function": "TIME_SERIES_DAILY", "symbol": symbol, "outputsize": "full"}
    s = parse(http.get_text(URL, params={**params, "apikey": key}), code)
    return s[s.index >= pd.Timestamp(start)]
