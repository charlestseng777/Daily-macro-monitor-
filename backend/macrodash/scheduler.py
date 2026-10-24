"""
Daily refresh at 05:30 UK time (Mon-Fri), before the London open.

Run standalone with `python -m macrodash scheduler`. Cron is set in
Europe/London, so it stays at 05:30 local across BST/GMT changes. Missed
runs (machine asleep) fire on wake within a two-hour grace window.
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import get_settings
from .db import Repository
from .pipeline import run

log = logging.getLogger(__name__)


def _job() -> None:
    try:
        run()
    except Exception:  # noqa: BLE001 - logged in run(); keep the scheduler alive
        log.error("scheduled refresh failed; will retry at the next slot")


def main(run_now: bool = False) -> None:
    s = get_settings()
    sched = BlockingScheduler(timezone=s.schedule_timezone)
    sched.add_job(_job, CronTrigger(day_of_week="mon-fri", hour=s.schedule_hour, minute=s.schedule_minute,
                                    timezone=s.schedule_timezone),
                  id="daily_refresh", misfire_grace_time=7200, coalesce=True, max_instances=1)
    # A safety retry an hour later catches providers that publish late.
    sched.add_job(_job, CronTrigger(day_of_week="mon-fri", hour=s.schedule_hour + 1, minute=s.schedule_minute,
                                    timezone=s.schedule_timezone),
                  id="retry_refresh", misfire_grace_time=3600, coalesce=True, max_instances=1)
    if run_now or Repository().latest_snapshot() is None:
        _job()
    log.info("scheduler started: weekdays %02d:%02d %s", s.schedule_hour, s.schedule_minute, s.schedule_timezone)
    sched.start()
