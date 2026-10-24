"""
Read-mostly JSON API.

/api/dashboard serves the latest precomputed snapshot from memory (refreshed
from the database every MACRO_API_CACHE_SECONDS), so it answers in
milliseconds. /api/series computes nothing new: it slices stored history
and attaches range statistics, all server-side.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import logging
import os
import threading
import time
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .. import instruments as reg
from .. import srs
from .. import seriesdata
from ..config import MACRO_ROOT, get_settings
from ..db import Repository
from ..logging_setup import configure

configure()
log = logging.getLogger(__name__)
settings = get_settings()

app = FastAPI(title="Global Macro Research API", version="1.0.0",
              description="Precomputed cross-asset analytics for the morning macro dashboard.")
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_origins, allow_methods=["GET", "POST"],
                   allow_headers=["*"])

_repo: Repository | None = None
_cache: dict = {"at": 0.0, "payload": None, "etag": None}
_lock = threading.Lock()

RANGES = seriesdata.RANGES


def repo() -> Repository:
    global _repo
    if _repo is None:
        _repo = Repository()
    return _repo


def _snapshot() -> tuple[dict | None, str | None]:
    with _lock:
        if _cache["payload"] is None or time.time() - _cache["at"] > settings.api_cache_seconds:
            payload = repo().latest_snapshot()
            if payload is not None:
                body = json.dumps(payload, separators=(",", ":"), default=str)
                _cache.update(at=time.time(), payload=payload, etag=hashlib.md5(body.encode()).hexdigest())
        return _cache["payload"], _cache["etag"]


# --------------------------------------------------------------- routes --

@app.get("/api/health")
def health() -> dict:
    payload, _ = _snapshot()
    last = repo().last_run()
    return {"status": "ok" if payload else "empty", "as_of": payload["meta"]["as_of"] if payload else None,
            "mode": payload["meta"]["mode"] if payload else None,
            "last_run": {k: str(v) for k, v in last.items() if k != "details"} if last else None}


@app.get("/api/dashboard")
def dashboard(request: Request, response: Response):
    payload, etag = _snapshot()
    if payload is None:
        raise HTTPException(503, "No snapshot yet. Run `python -m macrodash run` (or `run --demo`).")
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304)
    response.headers["ETag"] = etag or ""
    response.headers["Cache-Control"] = "public, max-age=60"
    return payload


def _series_payload(sid: str, rng: str) -> dict:
    got = seriesdata.load(repo(), sid)
    if got is None:
        raise HTTPException(404, f"unknown series {sid}")
    full, kind, label, unit = got
    if full.empty:
        raise HTTPException(404, f"no data for {sid}")
    return seriesdata.payload(sid, full, kind, label, unit, rng)


@app.get("/api/series/{sid}")
def series(sid: str, range: str = Query("1Y", alias="range")) -> dict:  # noqa: A002
    rng = range.upper()
    if rng not in RANGES:
        raise HTTPException(400, f"range must be one of {RANGES}")
    return _series_payload(sid, rng)


@app.get("/api/series")
def series_many(ids: str, range: str = Query("1Y", alias="range")) -> dict:  # noqa: A002
    rng = range.upper()
    if rng not in RANGES:
        raise HTTPException(400, f"range must be one of {RANGES}")
    wanted = [i for i in ids.split(",") if i][:8]
    return {"series": [_series_payload(i, rng) for i in wanted]}


@app.get("/api/instruments")
def instruments() -> dict:
    meta = repo().series_meta()
    return {"instruments": [
        {"id": i.id, "name": i.name, "short": i.short, "asset_class": i.asset_class, "region": i.region,
         "kind": i.kind, "unit": i.move_unit, "hidden": i.hidden,
         "source": (meta.get(i.id) or {}).get("source"), "last_date": str((meta.get(i.id) or {}).get("last_date") or "")}
        for i in reg.registry().values()]}


# ---------------------------------------------------------- flashcards --

class Review(BaseModel):
    grade: int = Field(ge=0, le=5)


@app.get("/api/flashcards/due")
def flashcards_due(limit: int = 20) -> dict:
    today = dt.date.today()
    cards = repo().due_flashcards(today, limit)
    return {"cards": [{"id": c["card_id"], "topic": c["topic"], "front": c["front"], "back": c["back"],
                       "reps": c["reps"], "interval_days": c["interval_days"], "due": str(c["due"])} for c in cards],
            "stats": repo().flashcard_stats(today)}


@app.post("/api/flashcards/{card_id}/review")
def flashcard_review(card_id: str, body: Review) -> dict:
    card = repo().get_flashcard(card_id)
    if not card:
        raise HTTPException(404, "unknown card")
    update = srs.review(card, body.grade, dt.date.today())
    repo().update_flashcard(card_id, **update)
    return {"id": card_id, **{k: str(v) for k, v in update.items()}}


# -------------------------------------------------------------- admin --

@app.post("/api/admin/refresh", status_code=202)
def refresh(background: BackgroundTasks, x_admin_token: str | None = Header(None)) -> dict:
    token = os.environ.get("MACRO_ADMIN_TOKEN")
    if not token or x_admin_token != token:
        raise HTTPException(403, "forbidden")
    from ..pipeline import run

    def job():
        run()
        _cache["at"] = 0.0
    background.add_task(job)
    return {"status": "started"}


# ------------------------------------------------- optional static site --

_dist = Path(os.environ.get("MACRO_WEB_DIST", MACRO_ROOT / "web" / "dist"))
if _dist.exists():
    app.mount("/", StaticFiles(directory=_dist, html=True), name="web")
