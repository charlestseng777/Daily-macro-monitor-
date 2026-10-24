"""U.S. Energy Information Administration API v2 (needs EIA_API_KEY)."""

from __future__ import annotations

import json

import pandas as pd

from ..config import get_settings
from .base import HttpClient, SourceError, clean_series

URL = "https://api.eia.gov/v2/seriesid/{code}"


def parse(text: str, code: str) -> pd.Series:
    data = json.loads(text).get("response", {}).get("data", [])
    if not data:
        raise SourceError(f"EIA {code}: no data")
    return clean_series({r["period"]: r.get("value") for r in data}, code)


def fetch(http: HttpClient, code: str, start: str) -> pd.Series:
    key = get_settings().eia_api_key
    if not key:
        raise SourceError("EIA_API_KEY not set")
    return parse(http.get_text(URL.format(code=code), params={"api_key": key, "start": start}), code)
