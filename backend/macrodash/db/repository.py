"""
All database access goes through Repository. Callers deal in pandas Series
and plain dicts; SQL stays here.
"""

from __future__ import annotations

import datetime as dt
from typing import Iterable

import pandas as pd
from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.engine import Engine

from ..config import get_settings
from .schema import fetch_runs, flashcards, metadata, observations, series_meta, snapshots

CHUNK = 2000


def _insert(engine: Engine):
    if engine.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    return insert


class Repository:
    def __init__(self, url: str | None = None):
        url = url or get_settings().database_url
        kwargs = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {"pool_pre_ping": True}
        self.engine = create_engine(url, future=True, **kwargs)
        metadata.create_all(self.engine)

    # ------------------------------------------------------- observations --
    def upsert_series(self, instrument_id: str, series: pd.Series, source: str) -> int:
        if series.empty:
            return 0
        rows = [{"instrument_id": instrument_id, "date": ts.date(), "value": float(v), "source": source}
                for ts, v in series.items()]
        insert = _insert(self.engine)
        with self.engine.begin() as conn:
            for i in range(0, len(rows), CHUNK):
                stmt = insert(observations).values(rows[i:i + CHUNK])
                stmt = stmt.on_conflict_do_update(
                    index_elements=["instrument_id", "date"],
                    set_={"value": stmt.excluded.value, "source": stmt.excluded.source})
                conn.execute(stmt)
            meta = insert(series_meta).values(
                instrument_id=instrument_id, source=source, first_date=rows[0]["date"],
                last_date=rows[-1]["date"], rows=len(rows), updated_at=dt.datetime.now(dt.UTC))
            conn.execute(meta.on_conflict_do_update(index_elements=["instrument_id"], set_={
                "source": meta.excluded.source, "last_date": meta.excluded.last_date,
                "rows": meta.excluded.rows, "updated_at": meta.excluded.updated_at}))
        return len(rows)

    def load_series(self, instrument_id: str, start: dt.date | None = None) -> pd.Series:
        q = select(observations.c.date, observations.c.value).where(observations.c.instrument_id == instrument_id)
        if start:
            q = q.where(observations.c.date >= start)
        with self.engine.connect() as conn:
            rows = conn.execute(q.order_by(observations.c.date)).all()
        s = pd.Series({pd.Timestamp(d): v for d, v in rows}, dtype="float64", name=instrument_id)
        s = s.sort_index()
        return s[s.index.dayofweek < 5] if len(s) else s

    def load_panel(self, ids: Iterable[str] | None = None) -> pd.DataFrame:
        """Wide frame: one column per instrument, indexed by date."""
        q = select(observations.c.instrument_id, observations.c.date, observations.c.value)
        if ids is not None:
            q = q.where(observations.c.instrument_id.in_(list(ids)))
        with self.engine.connect() as conn:
            rows = conn.execute(q).all()
        if not rows:
            return pd.DataFrame()
        frame = pd.DataFrame(rows, columns=["id", "date", "value"])
        frame["date"] = pd.to_datetime(frame["date"])
        frame = frame[frame["date"].dt.dayofweek < 5]   # weekend stamps are feed artefacts
        return frame.pivot_table(index="date", columns="id", values="value", aggfunc="last").sort_index()

    def series_meta(self) -> dict[str, dict]:
        with self.engine.connect() as conn:
            rows = conn.execute(select(series_meta)).mappings().all()
        return {r["instrument_id"]: dict(r) for r in rows}

    def clear_observations(self) -> None:
        with self.engine.begin() as conn:
            conn.execute(delete(observations))
            conn.execute(delete(series_meta))

    # ----------------------------------------------------------- runs ------
    def start_run(self, mode: str) -> int:
        with self.engine.begin() as conn:
            res = conn.execute(fetch_runs.insert().values(
                started_at=dt.datetime.now(dt.UTC), status="running", mode=mode))
            return int(res.inserted_primary_key[0])

    def finish_run(self, run_id: int, status: str, details: dict) -> None:
        with self.engine.begin() as conn:
            conn.execute(fetch_runs.update().where(fetch_runs.c.id == run_id).values(
                finished_at=dt.datetime.now(dt.UTC), status=status, details=details))

    def last_run(self) -> dict | None:
        with self.engine.connect() as conn:
            row = conn.execute(select(fetch_runs).order_by(fetch_runs.c.id.desc()).limit(1)).mappings().first()
        return dict(row) if row else None

    # ------------------------------------------------------- snapshots -----
    def save_snapshot(self, as_of: dt.date, mode: str, payload: dict, keep: int = 30) -> None:
        with self.engine.begin() as conn:
            conn.execute(snapshots.insert().values(as_of=as_of, created_at=dt.datetime.now(dt.UTC),
                                                   mode=mode, payload=payload))
            ids = [r[0] for r in conn.execute(select(snapshots.c.id).order_by(snapshots.c.id.desc())).all()]
            if len(ids) > keep:
                conn.execute(delete(snapshots).where(snapshots.c.id.in_(ids[keep:])))

    def latest_snapshot(self) -> dict | None:
        with self.engine.connect() as conn:
            row = conn.execute(select(snapshots.c.payload).order_by(snapshots.c.id.desc()).limit(1)).first()
        return row[0] if row else None

    def snapshot_history(self, limit: int = 10) -> list[dict]:
        with self.engine.connect() as conn:
            rows = conn.execute(select(snapshots.c.id, snapshots.c.as_of, snapshots.c.created_at, snapshots.c.mode)
                                .order_by(snapshots.c.id.desc()).limit(limit)).mappings().all()
        return [dict(r) for r in rows]

    # ------------------------------------------------------ flashcards -----
    def add_flashcards(self, cards: list[dict], today: dt.date) -> int:
        if not cards:
            return 0
        insert = _insert(self.engine)
        rows = [{"card_id": c["id"], "created": today, "topic": c["topic"], "front": c["front"],
                 "back": c["back"], "ease": 2.5, "interval_days": 0, "reps": 0, "lapses": 0, "due": today}
                for c in cards]
        with self.engine.begin() as conn:
            res = conn.execute(insert(flashcards).values(rows).on_conflict_do_nothing(index_elements=["card_id"]))
        return res.rowcount or 0

    def due_flashcards(self, today: dt.date, limit: int = 20) -> list[dict]:
        with self.engine.connect() as conn:
            rows = conn.execute(select(flashcards).where(flashcards.c.due <= today)
                                .order_by(flashcards.c.due, flashcards.c.created.desc()).limit(limit)).mappings().all()
        return [dict(r) for r in rows]

    def get_flashcard(self, card_id: str) -> dict | None:
        with self.engine.connect() as conn:
            row = conn.execute(select(flashcards).where(flashcards.c.card_id == card_id)).mappings().first()
        return dict(row) if row else None

    def update_flashcard(self, card_id: str, **values) -> None:
        with self.engine.begin() as conn:
            conn.execute(flashcards.update().where(flashcards.c.card_id == card_id).values(**values))

    def flashcard_stats(self, today: dt.date) -> dict:
        with self.engine.connect() as conn:
            total = conn.execute(select(func.count()).select_from(flashcards)).scalar() or 0
            due = conn.execute(select(func.count()).select_from(flashcards).where(flashcards.c.due <= today)).scalar() or 0
            mature = conn.execute(select(func.count()).select_from(flashcards)
                                  .where(flashcards.c.interval_days >= 21)).scalar() or 0
        return {"total": total, "due": due, "mature": mature}
