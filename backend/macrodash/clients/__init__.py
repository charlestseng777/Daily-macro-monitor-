"""
Data-provider registry. `SourceRouter.fetch(instrument)` walks the
instrument's source list in order and returns the first series that comes
back non-empty, along with the provider that supplied it.
"""

from __future__ import annotations

import logging

import pandas as pd

from ..config import get_settings
from ..instruments import Instrument
from . import alphavantage, cnbc, eia, fred, mof, sdmx, stooq, treasury, yahoo
from . import refinitiv as rdp
from .base import HttpClient, SourceError
from .boe import BoECurves, fetch_iadb

log = logging.getLogger(__name__)


class SourceRouter:
    def __init__(self, http: HttpClient | None = None, start: str | None = None):
        self.http = http or HttpClient.from_settings()
        self.start = start or get_settings().history_start
        self.boe_curves = BoECurves(self.http, self.start)
        self.rdp = rdp.RefinitivSession(self.http) if get_settings().refinitiv_configured else None
        self.failures: dict[str, list[str]] = {}

    def _call(self, provider: str, code: str, kind: str) -> pd.Series:
        h, start = self.http, self.start
        match provider:
            case "fred": return fred.fetch(h, code, start)
            case "treasury": return treasury.fetch(h, code, start)
            case "ecb": return sdmx.fetch_ecb(h, code, start)
            case "bundesbank": return sdmx.fetch_bundesbank(h, code, start)
            case "boe": return fetch_iadb(h, code, start)
            case "boe_curve": return self.boe_curves.point(code)
            case "mof": return mof.fetch(h, code, start)
            case "yahoo": return yahoo.fetch(h, code, start)
            case "stooq": return stooq.fetch(h, code, start)
            case "cnbc": return cnbc.fetch(h, code, start)
            case "eia": return eia.fetch(h, code, start)
            case "alphavantage": return alphavantage.fetch(h, code, start)
            case "refinitiv":
                if self.rdp is None:
                    raise SourceError("Refinitiv not configured")
                return rdp.fetch(self.rdp, code, start, kind)
        raise SourceError(f"unknown provider {provider!r}")

    MIN_ROWS = 30   # a source returning a handful of bars is not a history

    def fetch(self, inst: Instrument) -> tuple[pd.Series, str] | None:
        errors = []
        thin: tuple[pd.Series, str] | None = None
        for src in inst.sources:
            if src.provider == "refinitiv" and self.rdp is None:
                continue
            try:
                series = self._call(src.provider, src.code, inst.kind)
            except Exception as exc:  # noqa: BLE001 - any source failure falls through to the next
                errors.append(f"{src.provider}:{src.code}: {exc}")
                continue
            if len(series) >= self.MIN_ROWS:
                if errors:
                    log.info("%s: using %s after %d failed source(s)", inst.id, src.provider, len(errors))
                return series, f"{src.provider}:{src.code}"
            if len(series) and thin is None:
                thin = (series, f"{src.provider}:{src.code}")
            errors.append(f"{src.provider}:{src.code}: only {len(series)} rows")
        if thin is not None:
            # Better a short series than none (e.g. a monthly fallback).
            log.warning("%s: only a short history available (%s)", inst.id, thin[1])
            return thin
        self.failures[inst.id] = errors
        log.warning("%s: every source failed: %s", inst.id, " | ".join(errors) or "no usable sources")
        return None
