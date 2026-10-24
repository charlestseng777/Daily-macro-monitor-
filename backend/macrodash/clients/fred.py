"""FRED (St. Louis Fed). Uses the JSON API when FRED_API_KEY is set, the keyless
fredgraph CSV download otherwise. Missing observations are published as '.'."""

from __future__ import annotations

import io
import json

import pandas as pd

from ..config import get_settings
from .base import HttpClient, SourceError, clean_series

API = "https://api.stlouisfed.org/fred"
GRAPH = "https://fred.stlouisfed.org/graph/fredgraph.csv"


def parse_graph_csv(text: str, code: str) -> pd.Series:
    frame = pd.read_csv(io.StringIO(text), na_values=["."])
    if frame.shape[1] < 2:
        raise SourceError(f"FRED {code}: unexpected CSV layout")
    date_col = frame.columns[0]          # 'observation_date' (current) or 'DATE' (older)
    value_col = code if code in frame.columns else frame.columns[1]
    return clean_series(dict(zip(frame[date_col], pd.to_numeric(frame[value_col], errors="coerce"))), code)


def parse_api_json(text: str, code: str) -> pd.Series:
    payload = json.loads(text)
    if "observations" not in payload:
        raise SourceError(f"FRED {code}: {payload.get('error_message', 'no observations')}")
    values = {}
    for row in payload["observations"]:
        try:
            values[row["date"]] = float(row["value"])
        except (TypeError, ValueError):
            continue
    return clean_series(values, code)


def fetch(http: HttpClient, code: str, start: str) -> pd.Series:
    key = get_settings().fred_api_key
    if key:
        text = http.get_text(f"{API}/series/observations", params={
            "series_id": code, "api_key": key, "file_type": "json", "observation_start": start})
        return parse_api_json(text, code)
    return parse_graph_csv(http.get_text(GRAPH, params={"id": code, "cosd": start}), code)


def release_dates(http: HttpClient, release_id: str, start: str, end: str) -> list[str]:
    """Scheduled release dates (needs FRED_API_KEY)."""
    key = get_settings().fred_api_key
    if not key:
        return []
    text = http.get_text(f"{API}/release/dates", params={
        "release_id": release_id, "api_key": key, "file_type": "json",
        "realtime_start": start, "realtime_end": end,
        "include_release_dates_with_no_data": "true", "sort_order": "asc"})
    return [r["date"] for r in json.loads(text).get("release_dates", []) if start <= r["date"] <= end]
