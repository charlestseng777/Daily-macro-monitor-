"""CNBC chart service: daily history for government bond benchmarks that
have no free official daily feed (OAT, BTP, Bono, CGB) and a fallback for
Bunds and JGBs. Unofficial, so it sits behind official sources.
Codes are CNBC symbols, e.g. 'IT10Y-IT'."""

from __future__ import annotations

import json

import pandas as pd

from .base import HttpClient, SourceError, clean_series

URL = "https://ts-api.cnbc.com/harmony/app/charts/{range}.json"


def parse_chart(text: str, symbol: str) -> pd.Series:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SourceError(f"CNBC {symbol}: not JSON ({text[:80]!r})") from exc
    bars = (payload.get("barData") or {}).get("priceBars") or []
    values = {}
    for bar in bars:
        stamp = str(bar.get("tradeTime") or "")[:8]
        try:
            values[pd.Timestamp(stamp)] = float(bar.get("close"))
        except (TypeError, ValueError):
            continue
    if not values:
        raise SourceError(f"CNBC {symbol}: no price bars")
    return clean_series(values, symbol)


def fetch(http: HttpClient, code: str, start: str) -> pd.Series:
    # 5Y gives the longer (coarser) history; 1Y gives daily bars for the
    # window every statistic actually uses. Daily bars win where both exist.
    parts = []
    for rng in ("5Y", "1Y"):
        try:
            parts.append(parse_chart(http.get_text(URL.format(range=rng), params={"symbol": code}), code))
        except SourceError:
            continue
    if not parts:
        raise SourceError(f"CNBC {code}: no data")
    merged = pd.concat(parts)
    merged = merged[~merged.index.duplicated(keep="last")].sort_index()
    return merged[merged.index >= pd.Timestamp(start)]
