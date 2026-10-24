"""
Per-series statistics: moves over standard horizons, rolling volatility,
z-scores and percentile ranks, plus the sparkline points.

Units follow the instrument kind:
  * level kinds 'yield' / 'rate' / 'spread' are in percent -> moves in bp
  * 'bp' is a derived level already in basis points (curve slopes, spreads)
  * 'price' / 'fx' -> moves in percent
  * 'vol' (VIX) -> moves in index points
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

YEAR_OBS = 252
VOL_WINDOW = 20
SPARK_POINTS = 64

HORIZONS = {"d1": None, "w1": pd.DateOffset(days=7), "m1": pd.DateOffset(months=1),
            "m3": pd.DateOffset(months=3), "y1": pd.DateOffset(years=1)}


def move(new: float, old: float, kind: str) -> float:
    if kind in ("yield", "rate", "spread"):
        return (new - old) * 100.0
    if kind in ("price", "fx"):
        return (new / old - 1.0) * 100.0 if old else float("nan")
    return new - old          # 'bp' and 'vol'


def daily_moves(s: pd.Series, kind: str) -> pd.Series:
    if kind in ("yield", "rate", "spread"):
        return s.diff() * 100.0
    if kind in ("price", "fx"):
        return s.pct_change(fill_method=None) * 100.0
    return s.diff()


def value_on_or_before(s: pd.Series, when: pd.Timestamp) -> float | None:
    sub = s.loc[:when]
    return None if sub.empty else float(sub.iloc[-1])


def percentile_rank(window: pd.Series, value: float) -> float | None:
    """Share of observations in the window at or below `value`, 0-100."""
    w = window.dropna()
    if len(w) < 5:
        return None
    return float((w <= value).mean() * 100.0)


def rolling_zscore(s: pd.Series, window: int = YEAR_OBS) -> pd.Series:
    mean = s.rolling(window, min_periods=window // 4).mean()
    std = s.rolling(window, min_periods=window // 4).std()
    return (s - mean) / std.replace(0, np.nan)


def rolling_percentile(s: pd.Series, window: int = YEAR_OBS) -> pd.Series:
    return s.rolling(window, min_periods=window // 4).apply(lambda w: (w <= w[-1]).mean() * 100.0, raw=True)


def spark(s: pd.Series, n: int = SPARK_POINTS, lookback: pd.DateOffset = pd.DateOffset(months=3)) -> list[float]:
    """Evenly-sampled recent levels for a sparkline (oldest first)."""
    if s.empty:
        return []
    recent = s.loc[s.index[-1] - lookback:]
    if len(recent) > n:
        idx = np.linspace(0, len(recent) - 1, n).round().astype(int)
        recent = recent.iloc[idx]
    return [round(float(v), 4) for v in recent.values]


def _r(x: float | None, places: int = 2) -> float | None:
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return None
    return round(float(x), places)


@dataclass
class SeriesStats:
    last: float | None
    date: str | None
    prev_date: str | None
    d1: float | None
    w1: float | None
    m1: float | None
    m3: float | None
    ytd: float | None
    y1: float | None
    vol20: float | None          # stdev of daily moves, move units
    z_d1: float | None           # today's move in 20d-vol units
    z_level_1y: float | None     # level vs 1y mean, in 1y stdevs
    pct_1m: float | None
    pct_1y: float | None
    pct_all: float | None
    hi_1y: float | None
    lo_1y: float | None
    spark: list[float]

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def compute_stats(s: pd.Series, kind: str) -> SeriesStats | None:
    s = s.dropna()
    if len(s) < 2:
        return None
    last_ts = s.index[-1]
    last = float(s.iloc[-1])

    def chg(offset) -> float | None:
        if offset is None:
            old = float(s.iloc[-2])
        else:
            old = value_on_or_before(s, last_ts - offset)
            if old is None:
                return None
        return move(last, old, kind)

    ytd_base = value_on_or_before(s, pd.Timestamp(year=last_ts.year, month=1, day=1) - pd.Timedelta(days=1))
    moves = daily_moves(s, kind).dropna()
    vol = float(moves.iloc[-VOL_WINDOW:].std()) if len(moves) >= 5 else None
    d1 = move(last, float(s.iloc[-2]), kind)
    # Exclude today's move from the vol it is scored against.
    prior = moves.iloc[-VOL_WINDOW - 1:-1]
    base_vol = float(prior.std()) if len(prior) >= 5 else vol
    z_d1 = d1 / base_vol if base_vol and base_vol > 1e-9 else None

    year = s.loc[last_ts - pd.DateOffset(years=1):]
    month = s.loc[last_ts - pd.DateOffset(months=1):]
    z_level = None
    if len(year) >= 20 and year.std() > 1e-12:
        z_level = (last - year.mean()) / year.std()

    places = 4 if kind in ("yield", "rate", "spread", "fx") else 2
    return SeriesStats(
        last=_r(last, places), date=last_ts.date().isoformat(), prev_date=s.index[-2].date().isoformat(),
        d1=_r(d1), w1=_r(chg(HORIZONS["w1"])), m1=_r(chg(HORIZONS["m1"])), m3=_r(chg(HORIZONS["m3"])),
        ytd=_r(move(last, ytd_base, kind)) if ytd_base is not None else None, y1=_r(chg(HORIZONS["y1"])),
        vol20=_r(vol), z_d1=_r(z_d1), z_level_1y=_r(z_level),
        pct_1m=_r(percentile_rank(month, last), 0), pct_1y=_r(percentile_rank(year, last), 0),
        pct_all=_r(percentile_rank(s, last), 0),
        hi_1y=_r(float(year.max()), places), lo_1y=_r(float(year.min()), places), spark=spark(s),
    )


def align(*series: pd.Series, ffill_limit: int = 3) -> pd.DataFrame:
    """Join series on a common calendar. Different markets close on different
    holidays, so short gaps are carried forward (at most `ffill_limit` days)."""
    frame = pd.concat(series, axis=1).sort_index()
    return frame.ffill(limit=ffill_limit).dropna()


def difference_bp(a: pd.Series, b: pd.Series) -> pd.Series:
    """(a - b) in bp for two percent-level series, e.g. a curve slope or spread."""
    frame = align(a.rename("a"), b.rename("b"))
    return (frame["a"] - frame["b"]) * 100.0


def slice_range(s: pd.Series, rng: str) -> pd.Series:
    """Timeframe selector support: 1W 1M 3M 6M YTD 1Y 5Y MAX."""
    if s.empty:
        return s
    end = s.index[-1]
    rng = rng.upper()
    offsets = {"1W": pd.DateOffset(weeks=1), "1M": pd.DateOffset(months=1), "3M": pd.DateOffset(months=3),
               "6M": pd.DateOffset(months=6), "1Y": pd.DateOffset(years=1), "5Y": pd.DateOffset(years=5)}
    if rng == "YTD":
        return s.loc[pd.Timestamp(year=end.year, month=1, day=1):]
    if rng in offsets:
        return s.loc[end - offsets[rng]:]
    return s
