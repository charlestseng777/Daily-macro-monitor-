"""
The instrument registry: what each series is, how its moves are measured, and
where it can be fetched from. Loaded from macro/config/instruments.json so
source codes can be corrected without touching Python.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache

from .config import CONFIG_DIR

# How a move is expressed. Yields and spreads move in basis points; prices in
# percent; volatility indices in points.
BP_KINDS = {"yield", "rate", "spread"}
PCT_KINDS = {"price", "fx"}

REGION_NAMES = {
    "US": "United States", "UK": "United Kingdom", "EA": "Euro Area", "DE": "Germany",
    "JP": "Japan", "CN": "China", "FR": "France", "IT": "Italy", "ES": "Spain", "GLOBAL": "Global",
}


@dataclass(frozen=True)
class Source:
    provider: str
    code: str
    verify: bool = False


@dataclass(frozen=True)
class Instrument:
    id: str
    name: str
    short: str
    asset_class: str
    region: str
    kind: str
    sources: tuple[Source, ...]
    tenor: float | None = None
    risk_sign: int = 0
    fx_sign: int = 0
    hidden: bool = False
    demo: dict = field(default_factory=dict, hash=False, compare=False)

    @property
    def move_unit(self) -> str:
        if self.kind in BP_KINDS:
            return "bp"
        if self.kind in PCT_KINDS:
            return "%"
        return "pts"

    @property
    def level_unit(self) -> str:
        return "%" if self.kind in BP_KINDS else ""


def _parse(entry: dict) -> Instrument:
    sources = []
    for raw in entry.get("sources", []):
        provider, code = raw[0], raw[1]
        opts = raw[2] if len(raw) > 2 and isinstance(raw[2], dict) else {}
        sources.append(Source(provider, code, bool(opts.get("verify"))))
    return Instrument(
        id=entry["id"], name=entry["name"], short=entry.get("short", entry["name"]),
        asset_class=entry["asset_class"], region=entry["region"], kind=entry["kind"],
        sources=tuple(sources), tenor=entry.get("tenor"),
        risk_sign=int(entry.get("risk_sign", 0)), fx_sign=int(entry.get("fx_sign", 0)),
        hidden=bool(entry.get("hidden", False)), demo=entry.get("demo", {}),
    )


@lru_cache(maxsize=1)
def registry() -> dict[str, Instrument]:
    payload = json.loads((CONFIG_DIR / "instruments.json").read_text())
    items = [_parse(e) for e in payload["instruments"]]
    ids = [i.id for i in items]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise ValueError(f"duplicate instrument ids: {sorted(dupes)}")
    return {i.id: i for i in items}


def get(instrument_id: str) -> Instrument:
    return registry()[instrument_id]


@lru_cache(maxsize=1)
def central_banks() -> list[dict]:
    return json.loads((CONFIG_DIR / "central_banks.json").read_text())["banks"]


@lru_cache(maxsize=1)
def feeds() -> dict:
    return json.loads((CONFIG_DIR / "feeds.json").read_text())
