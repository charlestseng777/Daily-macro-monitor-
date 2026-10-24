"""U.S. Treasury daily par yield curve CSVs, one file per calendar year."""

from __future__ import annotations

import datetime as dt
import io

import pandas as pd

from .base import HttpClient, SourceError, clean_series

URL = ("https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
       "daily-treasury-rates.csv/{year}/all")


def parse_year_csv(text: str, column: str) -> pd.Series:
    frame = pd.read_csv(io.StringIO(text))
    if "Date" not in frame.columns or column not in frame.columns:
        raise SourceError(f"Treasury CSV missing 'Date' or '{column}'")
    dates = pd.to_datetime(frame["Date"], format="%m/%d/%Y", errors="coerce")
    return clean_series(dict(zip(dates, pd.to_numeric(frame[column], errors="coerce"))), column)


def fetch(http: HttpClient, code: str, start: str) -> pd.Series:
    first = int(start[:4])
    parts = []
    for year in range(first, dt.date.today().year + 1):
        text = http.get_text(URL.format(year=year), params={
            "type": "daily_treasury_yield_curve", "field_tdr_date_value": str(year), "page": "", "_format": "csv"})
        try:
            parts.append(parse_year_csv(text, code))
        except SourceError:
            continue
    if not parts:
        raise SourceError(f"Treasury: no data for {code}")
    return clean_series(pd.concat(parts), code)
