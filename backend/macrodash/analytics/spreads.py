"""Cross-country spreads, relative-value signals and forward rates."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .series import compute_stats, difference_bp, rolling_zscore


@dataclass(frozen=True)
class SpreadDef:
    id: str
    a: str
    b: str
    label: str
    group: str


SPREADS: tuple[SpreadDef, ...] = (
    SpreadDef("US10_DE10", "US10Y", "DE10Y", "UST 10Y − Bund", "core"),
    SpreadDef("UK10_DE10", "UK10Y", "DE10Y", "Gilt 10Y − Bund", "core"),
    SpreadDef("JP10_DE10", "JP10Y", "DE10Y", "JGB 10Y − Bund", "core"),
    SpreadDef("US2_DE2", "US2Y", "DE2Y", "UST 2Y − Schatz", "front"),
    SpreadDef("UK2_DE2", "UK2Y", "DE2Y", "Gilt 2Y − Schatz", "front"),
    SpreadDef("JP2_DE2", "JP2Y", "DE2Y", "JGB 2Y − Schatz", "front"),
    SpreadDef("FR10_DE10", "FR10Y", "DE10Y", "OAT − Bund", "periphery"),
    SpreadDef("IT10_DE10", "IT10Y", "DE10Y", "BTP − Bund", "periphery"),
    SpreadDef("ES10_DE10", "ES10Y", "DE10Y", "Bono − Bund", "periphery"),
)


def rv_signal(z_3m: float | None) -> str:
    if z_3m is None:
        return "n/a"
    if z_3m >= 1.5:
        return "wide vs 3M"
    if z_3m <= -1.5:
        return "tight vs 3M"
    return "in range"


def build_spreads(panel: pd.DataFrame) -> tuple[list[dict], dict[str, pd.Series]]:
    rows, series = [], {}
    for d in SPREADS:
        if d.a not in panel or d.b not in panel:
            continue
        s = difference_bp(panel[d.a].dropna(), panel[d.b].dropna())
        st = compute_stats(s, "bp")
        if st is None:
            continue
        series[d.id] = s
        z3 = rolling_zscore(s, 63).iloc[-1] if len(s) > 30 else None
        z3 = None if z3 is None or pd.isna(z3) else round(float(z3), 2)
        rows.append({"id": d.id, "label": d.label, "group": d.group, "a": d.a, "b": d.b,
                     **{k: st.as_dict()[k] for k in ("last", "date", "d1", "w1", "m1", "pct_1m", "pct_1y",
                                                     "z_d1", "spark", "hi_1y", "lo_1y")},
                     "z_3m": z3, "signal": rv_signal(z3)})
    return rows, series


# ------------------------------------------------------------- forwards --

def forward_rate(r1: float, t1: float, r2: float, t2: float) -> float:
    """Annually-compounded forward between t1 and t2 from two spot yields (%)."""
    g = ((1 + r2 / 100) ** t2 / (1 + r1 / 100) ** t1) ** (1 / (t2 - t1)) - 1
    return g * 100


FORWARDS = (
    ("US_1y1y", "US 1y1y", "US1Y", 1, "US2Y", 2),
    ("US_5y5y", "US 5y5y", "US5Y", 5, "US10Y", 10),
    ("US_10y20y", "US 10y20y", "US10Y", 10, "US30Y", 30),
    ("UK_5y5y", "UK 5y5y", "UK5Y", 5, "UK10Y", 10),
    ("DE_5y5y", "Germany 5y5y", "DE5Y", 5, "DE10Y", 10),
    ("JP_10y20y", "Japan 10y20y", "JP10Y", 10, "JP30Y", 30),
    ("US_BE_5y5y", "US 5y5y inflation", "US5YBE", 5, "US10YBE", 10),
)


def build_forwards(panel: pd.DataFrame) -> tuple[list[dict], dict[str, pd.Series]]:
    rows, series = [], {}
    for fid, label, a, ta, b, tb in FORWARDS:
        if a not in panel or b not in panel:
            continue
        frame = pd.concat([panel[a], panel[b]], axis=1).ffill(limit=3).dropna()
        if frame.empty:
            continue
        fwd = frame.apply(lambda r: forward_rate(r.iloc[0], ta, r.iloc[1], tb), axis=1)
        st = compute_stats(fwd, "yield")
        if st is None:
            continue
        series[fid] = fwd
        rows.append({"id": fid, "label": label, **{k: st.as_dict()[k] for k in ("last", "d1", "w1", "m1", "pct_1y", "spark")}})
    return rows, series
