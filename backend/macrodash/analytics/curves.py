"""
Yield-curve slopes and the bull/bear steepener/flattener taxonomy.

Definitions (moves over the same window, front leg F and back leg B):

  bear steepener  - curve steepens, led by the long end selling off (B up more than F)
  bull steepener  - curve steepens, led by the front end rallying (F down more than B)
  bear flattener  - curve flattens, led by the front end selling off (F up more than B)
  bull flattener  - curve flattens, led by the long end rallying (B down more than F)
  twist           - legs move in opposite directions (front down / back up, or vice versa)
  parallel        - slope change smaller than the threshold
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .series import compute_stats, difference_bp


@dataclass(frozen=True)
class CurveDef:
    id: str
    region: str
    front: str
    back: str
    label: str


CURVES: tuple[CurveDef, ...] = (
    CurveDef("US_2s10s", "US", "US2Y", "US10Y", "2s10s"),
    CurveDef("US_5s30s", "US", "US5Y", "US30Y", "5s30s"),
    CurveDef("US_10s30s", "US", "US10Y", "US30Y", "10s30s"),
    CurveDef("UK_2s10s", "UK", "UK2Y", "UK10Y", "2s10s"),
    CurveDef("UK_5s30s", "UK", "UK5Y", "UK30Y", "5s30s"),
    CurveDef("UK_10s30s", "UK", "UK10Y", "UK30Y", "10s30s"),
    CurveDef("DE_2s10s", "DE", "DE2Y", "DE10Y", "2s10s"),
    CurveDef("DE_5s30s", "DE", "DE5Y", "DE30Y", "5s30s"),
    CurveDef("JP_2s10s", "JP", "JP2Y", "JP10Y", "2s10s"),
    CurveDef("JP_10s30s", "JP", "JP10Y", "JP30Y", "10s30s"),
)

SHAPE_LABELS = {
    "bear_steepener": "Bear steepener", "bull_steepener": "Bull steepener",
    "bear_flattener": "Bear flattener", "bull_flattener": "Bull flattener",
    "twist_steepener": "Twist steepener", "twist_flattener": "Twist flattener",
    "parallel_up": "Parallel sell-off", "parallel_down": "Parallel rally", "unchanged": "Unchanged",
}

SHAPE_EXPLAIN = {
    "bear_steepener": "Long-end yields rose more than the front end: typically term premium, supply or inflation risk.",
    "bull_steepener": "Front-end yields fell more than the long end: the market is pricing more or earlier rate cuts.",
    "bear_flattener": "Front-end yields rose more than the long end: the market is pricing a more hawkish central bank.",
    "bull_flattener": "Long-end yields fell more than the front end: a growth scare, lower inflation risk or duration demand.",
    "twist_steepener": "Front end rallied while the long end sold off: easier policy expected but more long-run risk.",
    "twist_flattener": "Front end sold off while the long end rallied: tighter policy expected, weighing on growth.",
    "parallel_up": "Yields rose by similar amounts across the curve.",
    "parallel_down": "Yields fell by similar amounts across the curve.",
    "unchanged": "Little change at either end of the curve.",
}


def classify(d_front_bp: float | None, d_back_bp: float | None, threshold_bp: float = 0.5,
             still_bp: float = 0.5) -> str:
    """Classify a curve move from the moves in its two legs (bp)."""
    if d_front_bp is None or d_back_bp is None:
        return "unchanged"
    d_slope = d_back_bp - d_front_bp
    if abs(d_front_bp) < still_bp and abs(d_back_bp) < still_bp:
        return "unchanged"
    if abs(d_slope) < threshold_bp:
        return "parallel_up" if (d_front_bp + d_back_bp) > 0 else "parallel_down"
    if d_slope > 0:                                   # steepening
        if d_front_bp < 0 < d_back_bp:
            return "twist_steepener"
        return "bear_steepener" if d_back_bp > 0 else "bull_steepener"
    # flattening
    if d_back_bp < 0 < d_front_bp:
        return "twist_flattener"
    return "bear_flattener" if d_front_bp > 0 else "bull_flattener"


def build_curves(panel: pd.DataFrame, leg_stats: dict[str, dict]) -> tuple[list[dict], dict[str, pd.Series]]:
    rows, series = [], {}
    for c in CURVES:
        if c.front not in panel or c.back not in panel:
            continue
        slope = difference_bp(panel[c.back].dropna(), panel[c.front].dropna())
        st = compute_stats(slope, "bp")
        if st is None:
            continue
        series[c.id] = slope
        f, b = leg_stats.get(c.front, {}), leg_stats.get(c.back, {})
        shape_d = classify(f.get("d1"), b.get("d1"))
        shape_w = classify(f.get("w1"), b.get("w1"), threshold_bp=2.0, still_bp=2.0)
        rows.append({
            "id": c.id, "region": c.region, "label": c.label, "front": c.front, "back": c.back,
            **{k: st.as_dict()[k] for k in ("last", "date", "d1", "w1", "m1", "pct_1y", "pct_all", "z_d1", "spark")},
            "front_d1": f.get("d1"), "back_d1": b.get("d1"), "front_w1": f.get("w1"), "back_w1": b.get("w1"),
            "shape_d1": shape_d, "shape_d1_label": SHAPE_LABELS[shape_d], "shape_d1_explain": SHAPE_EXPLAIN[shape_d],
            "shape_w1": shape_w, "shape_w1_label": SHAPE_LABELS[shape_w],
            "inverted": st.last is not None and st.last < 0,
        })
    return rows, series


CURVE_TENORS = {
    "US": [("1Y", "US1Y"), ("2Y", "US2Y"), ("5Y", "US5Y"), ("10Y", "US10Y"), ("30Y", "US30Y")],
    "UK": [("2Y", "UK2Y"), ("5Y", "UK5Y"), ("10Y", "UK10Y"), ("30Y", "UK30Y")],
    "DE": [("2Y", "DE2Y"), ("5Y", "DE5Y"), ("10Y", "DE10Y"), ("30Y", "DE30Y")],
    "JP": [("1Y", "JP1Y"), ("2Y", "JP2Y"), ("10Y", "JP10Y"), ("30Y", "JP30Y")],
}


def curve_shapes(panel: pd.DataFrame) -> dict[str, dict]:
    """Each country's curve today, a week ago and a month ago (for the
    drill-down curve-shape chart)."""
    out = {}
    for region, legs in CURVE_TENORS.items():
        pts = []
        for label, iid in legs:
            if iid not in panel:
                continue
            s = panel[iid].dropna()
            if s.empty:
                continue
            end = s.index[-1]
            def at(off):
                sub = s.loc[: end - off]
                return round(float(sub.iloc[-1]), 3) if not sub.empty else None
            pts.append({"tenor": label, "id": iid, "today": round(float(s.iloc[-1]), 3),
                        "w1": at(pd.DateOffset(days=7)), "m1": at(pd.DateOffset(months=1)),
                        "y1": at(pd.DateOffset(years=1))})
        if pts:
            out[region] = {"points": pts}
    return out
