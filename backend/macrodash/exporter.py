"""
Portable history: one CSV per series plus the latest snapshot as JSON.

The GitHub Actions job (which has open internet access) runs the live
pipeline and commits these files, so any environment, including one whose
network blocks the data providers, can `import` them and serve real data.
CSV rows only ever append, which keeps the daily git diffs small.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd
from sqlalchemy import select

from .db import Repository
from .db.schema import observations

log = logging.getLogger(__name__)


def export(out: Path, repo: Repository | None = None) -> None:
    repo = repo or Repository()
    hist = out / "history"
    hist.mkdir(parents=True, exist_ok=True)
    with repo.engine.connect() as conn:
        rows = conn.execute(select(observations).order_by(observations.c.instrument_id, observations.c.date)).all()
    frame = pd.DataFrame(rows, columns=["id", "date", "value", "source"])
    for iid, grp in frame.groupby("id"):
        grp[["date", "value", "source"]].to_csv(hist / f"{iid}.csv", index=False, float_format="%.8g")
    snap = repo.latest_snapshot()
    if snap:
        (out / "dashboard.json").write_text(json.dumps(snap, indent=1, default=str))
    log.info("exported %d series to %s", frame["id"].nunique(), out)


def import_history(directory: Path, repo: Repository | None = None) -> int:
    repo = repo or Repository()
    total = 0
    for path in sorted((directory / "history").glob("*.csv")):
        frame = pd.read_csv(path)
        if frame.empty:
            continue
        s = pd.Series(frame["value"].values, index=pd.to_datetime(frame["date"]))
        total += repo.upsert_series(path.stem, s, str(frame["source"].iloc[-1]))
    return total
