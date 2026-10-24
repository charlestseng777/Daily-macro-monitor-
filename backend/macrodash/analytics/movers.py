"""Rank the day's moves across asset classes by their size relative to each
instrument's own recent volatility, so a 3bp move in JGBs and a 1% move in
the S&P are compared on the same footing."""

from __future__ import annotations

from ..instruments import Instrument

MOVER_CLASSES = {"rates", "fx", "equities", "commodities", "credit"}


def describe_move(inst: Instrument, d1: float) -> str:
    if inst.kind == "fx" and len(inst.short) == 6:
        base, quote = inst.short[:3], inst.short[3:]
        stronger = base if d1 > 0 else quote
        return f"{stronger} stronger"
    if inst.kind == "fx":
        return "dollar stronger" if d1 > 0 else "dollar weaker"
    if inst.kind == "spread":
        return "spreads wider" if d1 > 0 else "spreads tighter"
    if inst.kind == "yield":
        return "yields higher" if d1 > 0 else "yields lower"
    return "higher" if d1 > 0 else "lower"


def rank_movers(stats: dict[str, dict], registry: dict[str, Instrument], as_of: str, top: int = 5) -> dict:
    """`stats` should already be limited to recent prints; rows dated before
    `as_of` are flagged as lagged."""
    rows = []
    for iid, st in stats.items():
        inst = registry.get(iid)
        if not inst or inst.hidden or inst.asset_class not in MOVER_CLASSES:
            continue
        if st.get("z_d1") is None or st.get("d1") is None:
            continue
        rows.append({"id": iid, "name": inst.name, "short": inst.short, "asset_class": inst.asset_class,
                     "region": inst.region, "d1": st["d1"], "unit": inst.move_unit, "z": st["z_d1"],
                     "last": st["last"], "note": describe_move(inst, st["d1"]),
                     "date": st.get("date"), "lagged": st.get("date") != as_of})
    up = sorted((r for r in rows if r["z"] > 0), key=lambda r: -r["z"])[:top]
    down = sorted((r for r in rows if r["z"] < 0), key=lambda r: r["z"])[:top]
    overall = sorted(rows, key=lambda r: -abs(r["z"]))[:top]
    return {"up": up, "down": down, "top": overall}
