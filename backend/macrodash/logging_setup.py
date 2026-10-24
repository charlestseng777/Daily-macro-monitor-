"""One logging format for the scraper, the scheduler and the API."""

from __future__ import annotations

import logging
import os


def configure(level: str | None = None) -> None:
    logging.basicConfig(
        level=(level or os.environ.get("MACRO_LOG_LEVEL", "INFO")).upper(),
        format="%(asctime)s %(levelname)-7s %(name)s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # Third-party clients are chatty at INFO.
    for noisy in ("httpx", "httpcore", "apscheduler.executors.default"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
