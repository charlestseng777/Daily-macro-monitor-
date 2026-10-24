"""
Decompose nominal yield moves into inflation expectations (breakevens) and
real yields: d(nominal) = d(real) + d(breakeven).
"""

from __future__ import annotations

ATTRIBUTION_SETS = (
    # region, nominal, breakeven, real (None -> implied as nominal - breakeven)
    ("US", "US10Y", "US10YBE", "US10YREAL"),
    ("UK", "UK10Y", "UK10YBE", None),
    ("DE", "DE10Y", "DE10YBE", None),
)


def attribute(d_nominal: float | None, d_be: float | None, d_real: float | None) -> dict:
    """Classify what drove a nominal move. Inputs in bp."""
    if d_nominal is None or d_be is None:
        return {"driver": "unknown", "text": "Breakeven data unavailable."}
    if d_real is None:
        d_real = d_nominal - d_be
    if abs(d_nominal) < 1.0 and abs(d_be) < 1.0 and abs(d_real) < 1.0:
        return {"driver": "none", "d_real": round(d_real, 1), "d_be": round(d_be, 1),
                "text": "Little changed: neither real yields nor breakevens moved meaningfully."}
    direction = "rose" if d_nominal > 0 else "fell"
    if d_be * d_real < 0 and abs(d_nominal) < 0.5 * max(abs(d_be), abs(d_real)):
        bigger = "real yields" if abs(d_real) > abs(d_be) else "breakevens"
        return {"driver": "offsetting", "d_real": round(d_real, 1), "d_be": round(d_be, 1),
                "text": f"Offsetting moves: real yields {d_real:+.1f}bp against breakevens {d_be:+.1f}bp; "
                        f"{bigger} dominated."}
    share_be = d_be / d_nominal if d_nominal else 0.0
    if share_be >= 0.7:
        driver, why = "inflation", "inflation expectations"
    elif share_be <= 0.3:
        driver, why = "real", "real yields"
    else:
        driver, why = "both", "both real yields and inflation expectations"
    return {"driver": driver, "d_real": round(d_real, 1), "d_be": round(d_be, 1), "share_be": round(share_be, 2),
            "text": f"Nominal yields {direction} {abs(d_nominal):.1f}bp, driven by {why} "
                    f"(real {d_real:+.1f}bp, breakeven {d_be:+.1f}bp)."}


def build_attribution(stats: dict[str, dict]) -> list[dict]:
    out = []
    for region, nom, be, real in ATTRIBUTION_SETS:
        n, b = stats.get(nom), stats.get(be)
        if not n or not b:
            continue
        r = stats.get(real) if real else None
        for horizon in ("d1", "w1"):
            res = attribute(n.get(horizon), b.get(horizon), r.get(horizon) if r else None)
            out.append({"region": region, "horizon": horizon, "nominal": nom, "breakeven": be,
                        "d_nominal": n.get(horizon), **res})
    return out
