"""
Market regime classification.

Each regime is a signature: the direction each cross-asset factor should
move on a day of that type. Factors are measured as today's move in units of
its own 20-day volatility (z), clipped to +/-3 so one outlier cannot decide
the day alone. A regime's score is the weighted average agreement between
its signature and the observed z's; regimes whose defining factors
('require') did not move in the stated direction are excluded, so the
headline never contradicts the tape. The best score wins if it is convincing,
otherwise the day is 'Mixed' (or 'Quiet' if nothing moved).
"""

from __future__ import annotations

import numpy as np

# factor -> instrument (or derived series) whose z_d1 measures it
FACTORS = {
    "front_end": ["US2Y", "UK2Y", "DE2Y"],
    "long_end": ["US10Y", "UK10Y", "DE10Y"],
    "curve": ["US_2s10s", "UK_2s10s", "DE_2s10s"],
    "usd": ["DXY"],
    "equities": ["SPX", "SX5E", "FTSE", "NKY"],
    "credit_spreads": ["US_HY_OAS", "EU_HY_OAS"],
    "vol": ["VIX"],
    "gold": ["GOLD"],
    "oil": ["BRENT", "WTI"],
    "breakevens": ["US10YBE", "US5YBE"],
    "copper": ["COPPER"],
}

REGIMES = {
    "Hawkish repricing": {
        "tone": "hawkish",
        "sig": {"front_end": 1.0, "long_end": 0.6, "curve": -0.5, "usd": 0.7, "equities": -0.5, "gold": -0.4},
        "require": {"front_end": 1},
        "summary": "rates markets priced a more hawkish policy path"},
    "Dovish repricing": {
        "tone": "dovish",
        "sig": {"front_end": -1.0, "long_end": -0.6, "curve": 0.5, "usd": -0.7, "equities": 0.4, "gold": 0.4},
        "require": {"front_end": -1},
        "summary": "rates markets priced a more dovish policy path"},
    "Risk-on": {
        "tone": "risk_on",
        "sig": {"equities": 1.0, "credit_spreads": -0.8, "vol": -0.7, "long_end": 0.3, "oil": 0.3, "copper": 0.3},
        "require": {"equities": 1},
        "summary": "investors added risk across equities and credit"},
    "Risk-off / flight to quality": {
        "tone": "risk_off",
        "sig": {"equities": -1.0, "credit_spreads": 0.8, "vol": 0.8, "long_end": -0.6, "gold": 0.5, "usd": 0.3},
        "require": {"equities": -1, "long_end": -1},
        "summary": "investors cut risk and bought government bonds"},
    "Reflation / inflation repricing": {
        "tone": "inflation",
        "sig": {"breakevens": 1.0, "oil": 0.8, "long_end": 0.6, "curve": 0.5, "copper": 0.4},
        "require": {"breakevens": 1, "long_end": 1},
        "summary": "inflation expectations and commodities led yields higher"},
    "Growth scare": {
        "tone": "risk_off",
        "sig": {"long_end": -0.9, "oil": -0.6, "copper": -0.6, "equities": -0.6, "breakevens": -0.5, "curve": -0.3},
        "require": {"long_end": -1, "equities": -1},
        "summary": "growth worries pulled yields, commodities and equities lower"},
}

TONE_LABEL = {"hawkish": "Hawkish", "dovish": "Dovish", "risk_on": "Risk-on", "risk_off": "Risk-off",
              "inflation": "Inflation", "neutral": "Neutral"}


def factor_scores(z: dict[str, float | None]) -> dict[str, float]:
    out = {}
    for factor, ids in FACTORS.items():
        vals = [float(np.clip(z[i], -3, 3)) for i in ids if z.get(i) is not None]
        if vals:
            out[factor] = float(np.mean(vals))
    return out


def classify_regime(z: dict[str, float | None]) -> dict:
    f = factor_scores(z)
    if not f:
        return {"name": "Insufficient data", "tone": "neutral", "score": 0.0, "factors": {}, "drivers": [],
                "ranking": []}
    activity = float(np.mean([abs(v) for v in f.values()]))
    scored = []
    for name, spec in REGIMES.items():
        sig = {k: w for k, w in spec["sig"].items() if k in f}
        if len(sig) < 2:
            continue
        # A regime whose defining moves went the other way cannot describe
        # the day, however well the rest of its signature fits.
        if any(f.get(k, 0) * sign < 0.25 for k, sign in spec.get("require", {}).items()):
            continue
        total_w = sum(abs(w) for w in sig.values())
        score = sum(w * f[k] for k, w in sig.items()) / total_w
        contribs = sorted(((k, w * f[k]) for k, w in sig.items()), key=lambda kv: -kv[1])
        scored.append((score, name, spec, contribs))
    scored.sort(key=lambda t: -t[0])
    ranking = [{"name": n, "score": round(s, 2)} for s, n, _, _ in scored]

    factors = {k: round(v, 2) for k, v in f.items()}
    if activity < 0.5:
        return {"name": "Quiet / range-bound", "tone": "neutral", "score": round(activity, 2),
                "confidence": "low", "factors": factors, "drivers": [], "ranking": ranking,
                "summary": "cross-asset moves were small relative to recent volatility"}
    best = scored[0] if scored else None
    if best is None or best[0] < 0.45:
        return {"name": "Mixed / cross-currents", "tone": "neutral", "score": round(best[0] if best else 0, 2),
                "confidence": "low", "factors": factors, "ranking": ranking,
                "drivers": [k for k, _ in sorted(f.items(), key=lambda kv: -abs(kv[1]))[:3]],
                "summary": "markets moved without a single dominant theme"}
    score, name, spec, contribs = best
    margin = score - (scored[1][0] if len(scored) > 1 else 0)
    confidence = "high" if score >= 1.0 and margin >= 0.3 else "medium" if score >= 0.7 else "low"
    return {"name": name, "tone": spec["tone"], "tone_label": TONE_LABEL[spec["tone"]], "score": round(score, 2),
            "confidence": confidence, "factors": factors, "ranking": ranking,
            "drivers": [k for k, c in contribs if c > 0.3][:4], "summary": spec["summary"]}
