"""Table definitions (SQLAlchemy Core). Works on SQLite and PostgreSQL."""

from __future__ import annotations

from sqlalchemy import (JSON, Column, Date, DateTime, Float, Integer, MetaData, String, Table,
                        Text, func)

metadata = MetaData()

# One row per instrument per business day: the raw history every statistic is
# computed from. Stored locally so charts and percentiles never hit a provider.
observations = Table(
    "observations", metadata,
    Column("instrument_id", String(40), primary_key=True),
    Column("date", Date, primary_key=True),
    Column("value", Float, nullable=False),
    Column("source", String(120), nullable=False),
)

series_meta = Table(
    "series_meta", metadata,
    Column("instrument_id", String(40), primary_key=True),
    Column("source", String(120)),
    Column("first_date", Date),
    Column("last_date", Date),
    Column("rows", Integer),
    Column("updated_at", DateTime(timezone=True), server_default=func.now()),
)

# Audit log of every pipeline run.
fetch_runs = Table(
    "fetch_runs", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("started_at", DateTime(timezone=True), nullable=False),
    Column("finished_at", DateTime(timezone=True)),
    Column("status", String(20), nullable=False),
    Column("mode", String(20), nullable=False),
    Column("details", JSON),
)

# The fully-computed dashboard payload. The API serves the latest row as-is,
# which is what keeps page loads well under a second.
snapshots = Table(
    "snapshots", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("as_of", Date, nullable=False, index=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("mode", String(20), nullable=False),
    Column("payload", JSON, nullable=False),
)

# Spaced-repetition state per flashcard (SM-2).
flashcards = Table(
    "flashcards", metadata,
    Column("card_id", String(64), primary_key=True),
    Column("created", Date, nullable=False),
    Column("topic", String(40), nullable=False),
    Column("front", Text, nullable=False),
    Column("back", Text, nullable=False),
    Column("ease", Float, nullable=False, default=2.5),
    Column("interval_days", Integer, nullable=False, default=0),
    Column("reps", Integer, nullable=False, default=0),
    Column("lapses", Integer, nullable=False, default=0),
    Column("due", Date, nullable=False),
    Column("last_reviewed", Date),
)
