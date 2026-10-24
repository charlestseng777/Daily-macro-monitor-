"""Chart series shared by the API and the static-site export: any stored
instrument, curve slope, spread, forward or policy-pricing history, sliced to
a timeframe with its range statistics computed here, never in the browser."""

from __future__ import annotations

import pandas as pd

from . import instruments as reg
from .analytics.curves import CURVES
from .analytics.series import compute_stats, difference_bp, move, slice_range
from .analytics.spreads import FORWARDS, SPREADS, forward_rate
from .db import Repository

RANGES = ["1W", "1M", "3M", "6M", "YTD", "1Y", "5Y", "MAX"]


def all_ids(repo: Repository) -> list[str]:
    ids = [i for i in reg.registry()]
    ids += [c.id for c in CURVES] + [d.id for d in SPREADS] + [f[0] for f in FORWARDS]
    ids += [f"PRICING_{b['id']}_12M" for b in reg.central_banks()]
    return ids


def load(repo: Repository, sid: str) -> tuple[pd.Series, str, str, str] | None:
    """(full history, kind, label, level unit) or None for an unknown id."""
    registry = reg.registry()
    if sid in registry:
        inst = registry[sid]
        return repo.load_series(sid), inst.kind, inst.name, inst.level_unit
    for c in CURVES:
        if c.id == sid:
            return difference_bp(repo.load_series(c.back), repo.load_series(c.front)), "bp", f"{c.region} {c.label}", "bp"
    for d in SPREADS:
        if d.id == sid:
            return difference_bp(repo.load_series(d.a), repo.load_series(d.b)), "bp", d.label, "bp"
    for fid, label, a, ta, b, tb in FORWARDS:
        if fid == sid:
            frame = pd.concat([repo.load_series(a), repo.load_series(b)], axis=1).ffill(limit=3).dropna()
            s = frame.apply(lambda row: forward_rate(row.iloc[0], ta, row.iloc[1], tb), axis=1)
            return s, "yield", label, "%"
    if sid.startswith("PRICING_"):
        return repo.load_series(sid), "bp", sid.replace("PRICING_", "").replace("_12M", " priced over 12M"), "bp"
    return None


def move_unit(kind: str) -> str:
    return "bp" if kind in ("yield", "rate", "spread", "bp") else "%" if kind in ("price", "fx") else "pts"


def range_stats(full: pd.Series, kind: str, rng: str) -> tuple[pd.Series, dict]:
    window = slice_range(full, rng)
    change = move(float(window.iloc[-1]), float(window.iloc[0]), kind) if len(window) > 1 else None
    return window, {"change": None if change is None else round(change, 2), "high": round(float(window.max()), 4),
                    "low": round(float(window.min()), 4), "start": window.index[0].strftime("%Y-%m-%d"),
                    "end": window.index[-1].strftime("%Y-%m-%d"), "n": int(len(window))}


def points(s: pd.Series) -> list[dict]:
    return [{"t": ts.strftime("%Y-%m-%d"), "v": round(float(v), 4)} for ts, v in s.items()]


def payload(sid: str, full: pd.Series, kind: str, label: str, unit: str, rng: str) -> dict:
    window, stats = range_stats(full, kind, rng)
    st = compute_stats(full, kind)
    return {"id": sid, "label": label, "kind": kind, "unit": unit, "move_unit": move_unit(kind), "range": rng,
            "points": points(window), "range_stats": stats, "stats": st.as_dict() if st else None}


def static_payload(sid: str, full: pd.Series, kind: str, label: str, unit: str) -> dict:
    """Whole history once, plus each timeframe's start index and statistics,
    so a static site can switch timeframes by slicing at a given index."""
    ranges = {}
    for rng in RANGES:
        window, stats = range_stats(full, kind, rng)
        ranges[rng] = {**stats, "start_index": int(len(full) - len(window))}
    return {"id": sid, "label": label, "kind": kind, "unit": unit, "move_unit": move_unit(kind),
            "points": points(full), "ranges": ranges}
