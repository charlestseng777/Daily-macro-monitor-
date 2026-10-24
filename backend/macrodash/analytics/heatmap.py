"""Country x asset-class grid. Each cell is one representative instrument,
its daily move, the direction of the economically meaningful quantity, and
how unusual the move was."""

from __future__ import annotations

from ..instruments import Instrument

COUNTRIES = [("US", "United States"), ("UK", "United Kingdom"), ("EA", "Euro Area"), ("JP", "Japan"), ("CN", "China")]
COLUMNS = ["rates", "fx", "equities", "credit", "commodities"]

CELLS = {
    "US": {"rates": "US10Y", "fx": "DXY", "equities": "SPX", "credit": "US_HY_OAS", "commodities": "WTI"},
    "UK": {"rates": "UK10Y", "fx": "GBPUSD", "equities": "FTSE", "credit": "UK_CREDIT", "commodities": "BRENT"},
    "EA": {"rates": "DE10Y", "fx": "EURUSD", "equities": "SX5E", "credit": "EU_HY_OAS", "commodities": "TTF"},
    "JP": {"rates": "JP10Y", "fx": "USDJPY", "equities": "NKY", "credit": "JP_CREDIT", "commodities": "BRENT_JPY"},
    "CN": {"rates": "CN10Y", "fx": "USDCNY", "equities": "CSI300", "credit": "CN_CREDIT", "commodities": "COPPER"},
}

QUANTITY = {"rates": "10Y yield", "fx": "currency vs USD", "equities": "index", "credit": "spreads",
            "commodities": "price"}


def intensity(z: float | None) -> int:
    if z is None:
        return 0
    a = abs(z)
    return 3 if a >= 2.0 else 2 if a >= 1.0 else 1 if a >= 0.4 else 0


def build_heatmap(stats: dict[str, dict], registry: dict[str, Instrument]) -> dict:
    rows = []
    for code, name in COUNTRIES:
        cells = []
        for col in COLUMNS:
            iid = CELLS[code][col]
            st, inst = stats.get(iid), registry.get(iid)
            if not st or st.get("d1") is None or inst is None:
                cells.append({"column": col, "id": iid, "available": False})
                continue
            d1 = st["d1"]
            # Direction of the quantity a reader cares about.
            if col == "fx":
                sign = inst.fx_sign or 1
                value_dir = d1 * sign
            elif col == "credit" and inst.kind == "price":
                value_dir = -d1          # bond ETF price up = spreads tighter
            else:
                value_dir = d1
            direction = "up" if value_dir > 0 else "down" if value_dir < 0 else "flat"
            # Risk reading: equities up / spreads tighter = risk-on.
            risk = None
            if col == "equities":
                risk = "on" if d1 > 0 else "off"
            elif col == "credit":
                risk = "off" if value_dir > 0 else "on"
            cells.append({"column": col, "id": iid, "available": True, "name": inst.name, "short": inst.short,
                          "d1": d1, "value": value_dir if col == "fx" else d1, "unit": inst.move_unit, "z": st.get("z_d1"), "direction": direction,
                          "intensity": intensity(st.get("z_d1")), "risk": risk, "quantity": QUANTITY[col],
                          "proxy": "ETF price" if col == "credit" and inst.kind == "price" else None,
                          "date": st.get("date"), "lagged": bool(st.get("lagged"))})
        rows.append({"region": code, "name": name, "cells": cells})
    return {"columns": COLUMNS, "rows": rows}
