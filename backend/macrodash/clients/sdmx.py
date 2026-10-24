"""SDMX REST sources that speak SDMX-CSV: the ECB Data Portal and the
Deutsche Bundesbank. Codes are 'FLOW/KEY', e.g. 'EXR/D.USD.EUR.SP00.A'."""

from __future__ import annotations

import io
import re

import pandas as pd

from .base import HttpClient, SourceError, clean_series

ECB = "https://data-api.ecb.europa.eu/service/data/{flow}/{key}"
BUNDESBANK = "https://api.statistiken.bundesbank.de/rest/data/{flow}/{key}"
CSV_ACCEPT = "application/vnd.sdmx.data+csv;version=1.0.0"


def parse_sdmx_csv(text: str, code: str) -> pd.Series:
    frame = pd.read_csv(io.StringIO(text))
    if "TIME_PERIOD" not in frame.columns or "OBS_VALUE" not in frame.columns:
        raise SourceError(f"SDMX {code}: no TIME_PERIOD/OBS_VALUE columns ({text[:120]!r})")
    return clean_series(dict(zip(frame["TIME_PERIOD"], pd.to_numeric(frame["OBS_VALUE"], errors="coerce"))), code)


def parse_sdmx_xml(text: str, code: str) -> pd.Series:
    """SDMX-ML, structure-specific (<Obs TIME_PERIOD=.. OBS_VALUE=..>) or
    generic (<generic:Obs> with ObsDimension / ObsValue children)."""
    import xml.etree.ElementTree as ET

    root = ET.fromstring(text)
    values = {}
    for el in root.iter():
        tag = el.tag.rsplit("}", 1)[-1]
        if tag != "Obs":
            continue
        when, val = el.get("TIME_PERIOD"), el.get("OBS_VALUE")
        if when is None:
            for child in el:
                ctag = child.tag.rsplit("}", 1)[-1]
                if ctag == "ObsDimension":
                    when = child.get("value")
                elif ctag == "ObsValue":
                    val = child.get("value")
        try:
            values[when] = float(val)
        except (TypeError, ValueError):
            continue
    if not values:
        raise SourceError(f"SDMX {code}: no observations in XML")
    return clean_series(values, code)


def parse_any(text: str, code: str) -> pd.Series:
    text = text.lstrip("\ufeff")
    head = text.lstrip()[:200]
    first = text.split("\n", 1)[0]
    if head.startswith("<"):
        return parse_sdmx_xml(text, code)
    if "TIME_PERIOD" in first:
        # The Bundesbank serves SDMX-CSV with ';' separators.
        if ";" in first:
            frame = pd.read_csv(io.StringIO(text), sep=";", decimal="," if "," in text.split("\n", 2)[1] else ".")
            return clean_series(dict(zip(frame["TIME_PERIOD"], pd.to_numeric(frame["OBS_VALUE"], errors="coerce"))), code)
        return parse_sdmx_csv(text, code)
    # Bundesbank 'download' CSV: metadata lines, then 'YYYY-MM-DD,value[,flag]'.
    values = {}
    for line in text.splitlines():
        parts = [p.strip().strip('"') for p in line.split(";" if ";" in line else ",")]
        if len(parts) >= 2 and re.fullmatch(r"\d{4}-\d{2}-\d{2}", parts[0]):
            try:
                values[parts[0]] = float(parts[1].replace(",", "."))
            except ValueError:
                continue
    if not values:
        raise SourceError(f"SDMX {code}: unrecognised response ({head[:100]!r})")
    return clean_series(values, code)


def _split(code: str) -> tuple[str, str]:
    if "/" not in code:
        raise SourceError(f"SDMX code must be FLOW/KEY, got {code!r}")
    flow, key = code.split("/", 1)
    return flow, key


def fetch_ecb(http: HttpClient, code: str, start: str) -> pd.Series:
    flow, key = _split(code)
    text = http.get_text(ECB.format(flow=flow, key=key), params={"startPeriod": start, "format": "csvdata"})
    return parse_sdmx_csv(text, code)


def fetch_bundesbank(http: HttpClient, code: str, start: str) -> pd.Series:
    flow, key = _split(code)
    errors = []
    # SDMX-CSV first, then the API's default SDMX-ML.
    for headers in ({"Accept": CSV_ACCEPT}, {"Accept": "application/xml"}):
        try:
            text = http.get_text(BUNDESBANK.format(flow=flow, key=key), params={"startPeriod": start},
                                 headers=headers)
            return parse_any(text, code)
        except SourceError as exc:
            errors.append(str(exc))
    raise SourceError("; ".join(errors))
