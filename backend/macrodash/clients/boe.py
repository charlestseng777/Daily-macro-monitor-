"""
Bank of England.

* IADB (the Bank's statistical database): official Bank Rate, SONIA and a few
  par yields, as CSV.
* The published yield curves (Anderson-Sleath fitted gilt curves and the OIS
  curve), shipped as zipped Excel workbooks. Codes for these are
  'nominal:<years>', 'real:<years>' or 'inflation:<years>'.
"""

from __future__ import annotations

import datetime as dt
import io
import re
import zipfile

import pandas as pd

from .base import HttpClient, SourceError, clean_series

IADB = "https://www.bankofengland.co.uk/boeapps/database/_iadb-fromshowcolumns.asp"
CURVES = "https://www.bankofengland.co.uk/-/media/boe/files/statistics/yield-curves/"
ARCHIVES = {"nominal": "glcnominalddata.zip", "real": "glcrealddata.zip",
            "inflation": "glcinflationddata.zip", "ois": "oisddata.zip"}
LATEST = "latest-yield-curve-data.zip"


def parse_iadb_csv(text: str, code: str) -> pd.Series:
    frame = pd.read_csv(io.StringIO(text))
    if "DATE" not in frame.columns or code not in frame.columns:
        raise SourceError(f"BoE IADB {code}: unexpected layout ({list(frame.columns)[:3]})")
    dates = pd.to_datetime(frame["DATE"], format="%d %b %Y", errors="coerce")
    return clean_series(dict(zip(dates, pd.to_numeric(frame[code], errors="coerce"))), code)


def fetch_iadb(http: HttpClient, code: str, start: str) -> pd.Series:
    d = dt.date.fromisoformat(start)
    text = http.get_text(IADB, params={
        "csv.x": "yes", "Datefrom": d.strftime("%d/%b/%Y"), "Dateto": "now",
        "SeriesCodes": code, "CSVF": "TN", "UsingCodes": "Y", "VPD": "Y", "VFD": "N"})
    return parse_iadb_csv(text, code)


# ------------------------------------------------------------- curves ----

def _excel_date(value) -> dt.date | None:
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    try:
        days = int(float(value))
    except (TypeError, ValueError):
        return None
    if not 1 <= days <= 80000:
        return None
    return dt.date(1899, 12, 30) + dt.timedelta(days=days)


def _spot_sheet(names: list[str], short_end: bool) -> str:
    spot = [n for n in names if "spot" in n.lower()]
    for n in spot:
        if ("short" in n.lower()) == short_end:
            return n
    if spot:
        return spot[0]
    raise SourceError(f"no spot sheet in workbook ({names})")


def parse_curve_workbook(payload: bytes, start: dt.date, short_end: bool = False) -> dict[str, dict[float, float]]:
    """{ISO date: {tenor years: rate %}} from one BoE curve workbook. The
    header row is labelled 'years:' in column A; data rows start with a date."""
    from openpyxl import load_workbook

    book = load_workbook(io.BytesIO(payload), read_only=True, data_only=True)
    sheet = book[_spot_sheet(book.sheetnames, short_end)]
    tenors: dict[int, float] | None = None
    out: dict[str, dict[float, float]] = {}
    for row in sheet.iter_rows(values_only=True):
        if not row:
            continue
        label = str(row[0] or "").strip().lower()
        if label.startswith("years"):
            tenors = {}
            for i, v in enumerate(row[1:], start=1):
                try:
                    tenors[i] = float(v)
                except (TypeError, ValueError):
                    continue
            continue
        if not tenors:
            continue
        when = _excel_date(row[0])
        if when is None or when < start:
            continue
        point = {}
        for i, tenor in tenors.items():
            if i < len(row):
                try:
                    point[tenor] = float(row[i])
                except (TypeError, ValueError):
                    continue
        if point:
            out[when.isoformat()] = point
    book.close()
    return out


def _era_needed(name: str, start: dt.date) -> bool:
    if "present" in name.lower():
        return True
    years = [int(y) for y in re.findall(r"(19\d{2}|20\d{2})", name)]
    return not years or max(years) >= start.year


def parse_curve_zip(payload: bytes, kind: str, start: dt.date) -> dict[str, dict[float, float]]:
    out: dict[str, dict[float, float]] = {}
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        for name in archive.namelist():
            low = name.lower()
            if not low.endswith(".xlsx") or kind not in low or not _era_needed(name, start):
                continue
            for d, pts in parse_curve_workbook(archive.read(name), start, short_end=(kind == "ois")).items():
                out.setdefault(d, {}).update(pts)
    return out


class BoECurves:
    """Downloads each curve archive at most once per pipeline run."""

    def __init__(self, http: HttpClient, start: str):
        self.http = http
        self.start = dt.date.fromisoformat(start)
        self._curves: dict[str, dict[str, dict[float, float]]] = {}

    def curves(self, kind: str) -> dict[str, dict[float, float]]:
        if kind not in self._curves:
            data = parse_curve_zip(self.http.get(CURVES + ARCHIVES[kind]), kind, self.start)
            try:
                for d, pts in parse_curve_zip(self.http.get(CURVES + LATEST), kind, self.start).items():
                    data.setdefault(d, {}).update(pts)
            except SourceError:
                pass
            if not data:
                raise SourceError(f"BoE {kind} curve: no data")
            self._curves[kind] = data
        return self._curves[kind]

    def point(self, code: str) -> pd.Series:
        kind, tenor = code.split(":")
        t = float(tenor)
        values = {d: pts[t] for d, pts in self.curves(kind).items() if t in pts}
        if not values:
            raise SourceError(f"BoE {kind} curve has no {tenor}Y point")
        return clean_series(values, code)

    def ois_latest(self) -> tuple[str, list[tuple[float, float]]]:
        data = self.curves("ois")
        last = max(data)
        return last, sorted(data[last].items())
