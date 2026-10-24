"""
DEMO DATA: synthetic, clearly labelled, never mixed with live data.

Used for local development, tests and screenshots when the real providers
are unreachable. A small factor model (global rates, regional rates, front-end
policy, dollar, risk appetite, oil, inflation) drives every instrument, so the
cross-asset relationships the narrative engine looks for are present. The
final day carries a scripted 'hawkish US data surprise' so the demo
commentary has something to say.

Every payload built from this data is stamped mode='demo' and the UI shows
a DEMO DATA banner.
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

from ..instruments import Instrument

FACTORS = ["global_rates", "us_rates", "uk_rates", "eu_rates", "jp_rates", "us_front", "uk_front", "eu_front",
           "usd", "risk", "oil", "inflation", "china", "periphery"]

# The last day's scripted shocks, in factor standard deviations.
SCENARIO = {"us_front": 2.6, "us_rates": 1.4, "global_rates": 0.9, "usd": 1.6, "risk": -1.3, "oil": 0.4,
            "inflation": 0.3, "uk_front": 0.5, "periphery": 1.2, "china": -0.4}


def _loadings(inst: Instrument) -> dict[str, float]:
    r, k, a = inst.region, inst.kind, inst.asset_class
    L: dict[str, float] = {}
    if a in ("rates", "money") and k == "yield":
        L["global_rates"] = 0.45
        reg = {"US": "us_rates", "UK": "uk_rates", "DE": "eu_rates", "EA": "eu_rates", "FR": "eu_rates",
               "IT": "eu_rates", "ES": "eu_rates", "JP": "jp_rates"}.get(r)
        if reg:
            L[reg] = 0.55
        front = {"US": "us_front", "UK": "uk_front", "DE": "eu_front", "EA": "eu_front"}.get(r)
        if front and (inst.tenor or 10) <= 5:
            L[front] = 0.9 if (inst.tenor or 10) <= 2 else 0.45
        if r in ("IT", "ES", "FR"):
            L["periphery"] = {"IT": 0.9, "ES": 0.6, "FR": 0.4}[r]
        if r == "CN":
            L = {"china": 0.6, "global_rates": 0.1}
        if r == "JP":
            L["global_rates"] = 0.2
    elif a == "inflation":
        L = {"inflation": 0.7, "oil": 0.35, "us_rates": 0.15}
        if inst.id == "US10YREAL":
            L = {"us_rates": 0.6, "global_rates": 0.4, "us_front": 0.3, "inflation": -0.35}
    elif a == "fx":
        if inst.id == "DXY":
            L = {"usd": 0.9, "us_front": 0.25}
        elif inst.id == "USDJPY":
            L = {"usd": 0.6, "us_rates": 0.35, "risk": 0.25, "jp_rates": -0.3}
        elif inst.id == "USDCNY":
            L = {"usd": 0.5, "china": -0.4}
        else:
            L = {"usd": -0.8, "uk_front" if r == "UK" else "eu_front": 0.2, "risk": 0.1}
    elif a == "equities":
        L = {"risk": 0.85, "us_rates": -0.15}
        if inst.kind == "vol":
            L = {"risk": -0.9}
        if r == "CN":
            L = {"risk": 0.4, "china": 0.7}
        if r == "JP":
            L["usd"] = 0.2
    elif a == "commodities":
        L = {"oil": 0.9, "risk": 0.15}
        if inst.id == "GOLD":
            L = {"usd": -0.45, "us_rates": -0.35, "risk": -0.2, "inflation": 0.2}
        elif inst.id == "COPPER":
            L = {"china": 0.6, "risk": 0.4}
        elif inst.id == "TTF":
            L = {"oil": 0.5}
    elif a == "credit":
        L = {"risk": 0.8 if k == "price" else -0.8}
    return L


def business_days(end: dt.date, years: int = 6) -> pd.DatetimeIndex:
    return pd.bdate_range(end=end, periods=years * 260)


def generate(registry: dict[str, Instrument], end: dt.date | None = None, seed: int = 7) -> dict[str, pd.Series]:
    # The most recent weekday on or before `end` (default: today).
    end = pd.offsets.BDay().rollback(pd.Timestamp(end or dt.date.today())).date()
    idx = business_days(end)
    n = len(idx)
    rng = np.random.default_rng(seed)
    f = pd.DataFrame(rng.standard_normal((n, len(FACTORS))), index=idx, columns=FACTORS)
    for name, shock in SCENARIO.items():
        f.iloc[-1, f.columns.get_loc(name)] = shock

    out: dict[str, pd.Series] = {}
    for inst in registry.values():
        if not inst.demo or inst.sources and inst.sources[0].provider == "derived":
            continue
        level, vol = float(inst.demo["level"]), float(inst.demo.get("vol", 0))
        if inst.kind == "rate" and vol == 0:
            out[inst.id] = _policy_steps(idx, level, rng)
            continue
        load = _loadings(inst)
        common = sum(w * f[k] for k, w in load.items()) if load else 0.0
        explained = min(sum(w * w for w in load.values()), 0.95) if load else 0.0
        eps = common + np.sqrt(1 - explained) * rng.standard_normal(n)
        eps = pd.Series(eps, index=idx)
        if inst.kind in ("price", "fx", "vol"):
            # Log random walk, gently pulled back to the target level.
            x = np.empty(n)
            x[-1] = np.log(level)
            # Walk backwards from today's level so the series ends exactly there.
            for t in range(n - 1, 0, -1):
                x[t - 1] = x[t] - vol * eps.iloc[t] - 0.004 * (x[t] - np.log(level))
            out[inst.id] = pd.Series(np.exp(x), index=idx).round(4)
        else:
            x = np.empty(n)
            x[-1] = level
            for t in range(n - 1, 0, -1):
                x[t - 1] = x[t] - vol * eps.iloc[t] - 0.006 * (x[t] - level)
            out[inst.id] = pd.Series(x, index=idx).round(4)

    # Overnight fixings sit just under their policy rates.
    for on, pol, gap in (("SOFR", "FED_UPPER", 0.13), ("EFFR", "FED_UPPER", 0.17), ("SONIA", "BANK_RATE", 0.03),
                         ("ESTR", "ECB_DFR", 0.07)):
        if pol in out and on in registry:
            noise = pd.Series(rng.normal(0, 0.004, n), index=idx)
            out[on] = (out[pol] - gap + noise).round(4)
    if "BRENT" in out and "USDJPY" in out:
        out["BRENT_JPY"] = (out["BRENT"] * out["USDJPY"]).round(2)
    return out


def _policy_steps(idx: pd.DatetimeIndex, final: float, rng) -> pd.Series:
    """A policy-rate history that steps down 25bp at a time to `final`."""
    n = len(idx)
    values = np.full(n, final)
    level = final
    t = n - 1 - int(rng.integers(40, 90))
    while t > 0 and level < final + 1.5:
        level += 0.25
        values[:t] = level
        t -= int(rng.integers(35, 80))
    return pd.Series(values, index=idx)


# ------------------------------------------------- policy pricing (demo) --

DEMO_PATHS = {  # cumulative bp priced after each of the next meetings, before today's shock
    "FED": [-14, -30, -42, -50, -55, -58, -58, -58],
    "BOE": [-9, -22, -35, -44, -50, -50, -50, -50],
    "ECB": [-2, -4, -6, -7, -7, -6, -5, -4],
    "BOJ": [6, 14, 21, 27, 31, 35, 38, 40],
}
DEMO_SHOCK_BP = {"FED": 9, "BOE": 3, "ECB": 1, "BOJ": 1}


def demo_ois_nodes(bank: str, today: dt.date, meetings: list[dt.date], overnight: float,
                   shocked: bool = True) -> list[tuple[float, float]]:
    """Synthetic OIS spot nodes consistent with DEMO_PATHS (step path ->
    discount factors -> spot rates at 1, 3, 6, 9, 12, 18, 24 months)."""
    path = list(DEMO_PATHS[bank])
    if shocked:
        shock = DEMO_SHOCK_BP[bank]
        path = [p + shock * min(1.0, (i + 1) / 3) for i, p in enumerate(path)]
    future = [m for m in sorted(meetings) if m > today][: len(path)]
    nodes = []
    for months in (1, 3, 6, 9, 12, 18, 24):
        t_end = today + dt.timedelta(days=int(months * 30.5))
        acc, prev_t, rate = 0.0, today, overnight
        for m, cum in zip(future, path):
            if m >= t_end:
                break
            acc += rate * (m - prev_t).days
            prev_t, rate = m, overnight + cum / 100.0
        acc += rate * (t_end - prev_t).days
        nodes.append((months / 12.0, acc / (t_end - today).days))
    return nodes
