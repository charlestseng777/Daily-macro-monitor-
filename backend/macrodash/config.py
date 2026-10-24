"""
Runtime settings, read once from the environment.

Every secret (API keys, the Refinitiv app key, the database URL) comes from
environment variables, never from source. `.env` in macro/ is loaded for local
work if python-dotenv is installed; in CI and on servers the variables are set
directly.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

MACRO_ROOT = Path(__file__).resolve().parents[2]          # .../macro
CONFIG_DIR = MACRO_ROOT / "config"
DATA_DIR = MACRO_ROOT / "data"

try:  # optional for local development only
    from dotenv import load_dotenv

    load_dotenv(MACRO_ROOT / ".env")
except ImportError:  # pragma: no cover
    pass


def _bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class Settings:
    database_url: str
    cache_dir: Path
    cache_ttl_hours: int
    http_timeout: int
    http_retries: int
    history_start: str
    demo_mode: bool

    fred_api_key: str | None
    eia_api_key: str | None
    alphavantage_api_key: str | None
    tradingeconomics_api_key: str | None

    refinitiv_app_key: str | None
    refinitiv_username: str | None
    refinitiv_password: str | None
    refinitiv_client_id: str | None
    refinitiv_client_secret: str | None
    refinitiv_take_session: bool

    anthropic_api_key: str | None
    anthropic_model: str
    llm_enabled: bool

    allowed_origins: list[str] = field(default_factory=lambda: ["*"])
    api_cache_seconds: int = 60
    schedule_hour: int = 5
    schedule_minute: int = 30
    schedule_timezone: str = "Europe/London"

    @property
    def refinitiv_configured(self) -> bool:
        return bool(
            (self.refinitiv_client_id and self.refinitiv_client_secret)
            or (self.refinitiv_username and self.refinitiv_password and self.refinitiv_app_key)
        )

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


def _database_url() -> str:
    url = os.environ.get("MACRO_DATABASE_URL") or os.environ.get("DATABASE_URL") or ""
    if not url:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{DATA_DIR / 'macro.db'}"
    # Render and Heroku hand out postgres:// URLs; SQLAlchemy wants the driver.
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    env = os.environ.get
    origins = [o.strip() for o in env("ALLOWED_ORIGINS", "*").split(",") if o.strip()]
    return Settings(
        database_url=_database_url(),
        cache_dir=Path(env("MACRO_CACHE_DIR", str(DATA_DIR / "cache"))),
        cache_ttl_hours=_int("MACRO_CACHE_TTL_HOURS", 6),
        http_timeout=_int("MACRO_HTTP_TIMEOUT", 30),
        http_retries=_int("MACRO_HTTP_RETRIES", 4),
        history_start=env("MACRO_HISTORY_START", "2015-01-01"),
        demo_mode=_bool("MACRO_DEMO_MODE"),
        fred_api_key=env("FRED_API_KEY") or None,
        eia_api_key=env("EIA_API_KEY") or None,
        alphavantage_api_key=env("ALPHAVANTAGE_API_KEY") or None,
        tradingeconomics_api_key=env("TRADINGECONOMICS_API_KEY") or None,
        refinitiv_app_key=env("REFINITIV_APP_KEY") or None,
        refinitiv_username=env("REFINITIV_USERNAME") or None,
        refinitiv_password=env("REFINITIV_PASSWORD") or None,
        refinitiv_client_id=env("REFINITIV_CLIENT_ID") or None,
        refinitiv_client_secret=env("REFINITIV_CLIENT_SECRET") or None,
        refinitiv_take_session=_bool("MACRO_REFINITIV_TAKE_SESSION"),
        anthropic_api_key=env("ANTHROPIC_API_KEY") or None,
        anthropic_model=env("ANTHROPIC_MODEL", "claude-opus-5-5"),
        llm_enabled=_bool("MACRO_LLM_ENABLED", True),
        allowed_origins=origins or ["*"],
        api_cache_seconds=_int("MACRO_API_CACHE_SECONDS", 60),
        schedule_hour=_int("MACRO_SCHEDULE_HOUR", 5),
        schedule_minute=_int("MACRO_SCHEDULE_MINUTE", 30),
        schedule_timezone=env("MACRO_SCHEDULE_TZ", "Europe/London"),
    )
