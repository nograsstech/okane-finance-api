"""
Backtest notification scheduler.

Runs strategy_notification_job on a session-aware schedule:
  - Every 5 min during London open  (Mon–Fri 07:00–10:00 UTC)
  - Every 5 min during NY open      (Mon–Fri 13:30–16:30 UTC)

Multiple APScheduler jobs with non-overlapping cron windows cover each
session exactly, using max_instances=1 and coalesce=True so a slow run
never stacks up.
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)


async def _run_notification_job() -> None:
    from app.signals.service import strategy_notification_job

    logger.info("Scheduled strategy_notification_job started")
    try:
        await strategy_notification_job()
        logger.info("Scheduled strategy_notification_job completed")
    except Exception as exc:
        logger.error("Scheduled strategy_notification_job failed: %s", exc, exc_info=True)


def _add_london_open_jobs(scheduler: AsyncIOScheduler) -> None:
    """Every 5 min Mon–Fri 07:00–09:55 UTC (London opening session)."""
    scheduler.add_job(
        _run_notification_job,
        CronTrigger(day_of_week="mon-fri", hour="7-9", minute="*/5", timezone="UTC"),
        id="notify_london",
        max_instances=1,
        coalesce=True,
    )


def _add_ny_open_jobs(scheduler: AsyncIOScheduler) -> None:
    """Every 5 min Mon–Fri 13:30–16:30 UTC (New York opening session)."""
    # 13:30 – 13:55
    scheduler.add_job(
        _run_notification_job,
        CronTrigger(
            day_of_week="mon-fri", hour="13", minute="30,35,40,45,50,55", timezone="UTC"
        ),
        id="notify_ny_open",
        max_instances=1,
        coalesce=True,
    )
    # 14:00 – 15:55
    scheduler.add_job(
        _run_notification_job,
        CronTrigger(day_of_week="mon-fri", hour="14-15", minute="*/5", timezone="UTC"),
        id="notify_ny_mid",
        max_instances=1,
        coalesce=True,
    )
    # 16:00 – 16:30
    scheduler.add_job(
        _run_notification_job,
        CronTrigger(
            day_of_week="mon-fri", hour="16", minute="0,5,10,15,20,25,30", timezone="UTC"
        ),
        id="notify_ny_close",
        max_instances=1,
        coalesce=True,
    )


def build_scheduler() -> AsyncIOScheduler:
    """Return a configured (but not yet started) AsyncIOScheduler."""
    scheduler = AsyncIOScheduler(timezone="UTC")
    _add_london_open_jobs(scheduler)
    _add_ny_open_jobs(scheduler)
    return scheduler
