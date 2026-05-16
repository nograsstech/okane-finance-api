"""
Unit tests for the backtest notification scheduler.

Verifies that build_scheduler() creates jobs covering the expected
London and NY opening-session windows without needing a running event loop
or live database connection.
"""

from __future__ import annotations

import pytest
from apscheduler.triggers.cron import CronTrigger

from app.scheduler import build_scheduler


def _job_ids(scheduler) -> set[str]:
    return {job.id for job in scheduler.get_jobs()}


def _trigger_fires_at(
    trigger: CronTrigger,
    hour: int,
    minute: int,
    year: int = 2024,
    month: int = 1,
    day: int = 8,
) -> bool:
    """
    Return True if the trigger would fire at the given UTC datetime.

    Defaults to Monday 2024-01-08 (EST, UTC-5). Pass a summer date
    (e.g. month=7, day=8) to test EDT (UTC-4) behaviour.
    """
    from datetime import datetime, timezone

    dt = datetime(year, month, day, hour, minute, 0, tzinfo=timezone.utc)
    # prev_fire_time=None so APScheduler evaluates from epoch start
    next_fire = trigger.get_next_fire_time(None, dt)
    # The trigger fires AT dt if next_fire equals dt exactly
    return next_fire == dt


class TestBuildScheduler:
    def test_returns_scheduler_instance(self):
        from apscheduler.schedulers.asyncio import AsyncIOScheduler

        scheduler = build_scheduler()
        assert isinstance(scheduler, AsyncIOScheduler)

    def test_expected_job_ids_present(self):
        scheduler = build_scheduler()
        ids = _job_ids(scheduler)
        assert "notify_london" in ids
        assert "notify_ny_open" in ids
        assert "notify_ny_mid" in ids
        assert "notify_ny_close" in ids

    def test_no_extra_jobs(self):
        scheduler = build_scheduler()
        assert _job_ids(scheduler) == {
            "notify_london",
            "notify_ny_open",
            "notify_ny_mid",
            "notify_ny_close",
        }

    def test_all_jobs_have_max_instances_one(self):
        scheduler = build_scheduler()
        for job in scheduler.get_jobs():
            assert job.max_instances == 1, f"Job {job.id!r} has max_instances != 1"

    def test_all_jobs_coalesce(self):
        scheduler = build_scheduler()
        for job in scheduler.get_jobs():
            assert job.coalesce is True, f"Job {job.id!r} does not coalesce"


class TestLondonSessionCoverage:
    """notify_london should fire every 5 min from 07:00 to 09:55 UTC."""

    def _london_trigger(self) -> CronTrigger:
        return build_scheduler().get_job("notify_london").trigger

    @pytest.mark.parametrize("hour,minute", [
        (7, 0), (7, 5), (7, 30), (7, 55),
        (8, 0), (8, 25), (8, 50),
        (9, 0), (9, 45), (9, 55),
    ])
    def test_fires_during_london_session(self, hour, minute):
        assert _trigger_fires_at(self._london_trigger(), hour, minute)

    @pytest.mark.parametrize("hour,minute", [
        (6, 55),   # before session
        (10, 0),   # after session (07-09 range excludes hour 10)
        (11, 0),
    ])
    def test_does_not_fire_outside_london_session(self, hour, minute):
        assert not _trigger_fires_at(self._london_trigger(), hour, minute)


class TestNYSessionCoverage:
    """NY session jobs fire every 5 min at 09:30–12:30 America/New_York.

    DST sanity:
      Summer (EDT, UTC-4): 09:30 NY = 13:30 UTC  (e.g. 2024-07-08)
      Winter (EST, UTC-5): 09:30 NY = 14:30 UTC  (e.g. 2024-01-08)
    """

    def _get_trigger(self, job_id: str) -> CronTrigger:
        return build_scheduler().get_job(job_id).trigger

    # --- Summer (EDT) sanity: NY open = 13:30 UTC ---

    @pytest.mark.parametrize("hour,minute", [
        (13, 30), (13, 35), (13, 55),
    ])
    def test_ny_open_fires_edt(self, hour, minute):
        # Summer Monday (EDT = UTC-4): 09:30–09:55 NY = 13:30–13:55 UTC
        assert _trigger_fires_at(
            self._get_trigger("notify_ny_open"), hour, minute, year=2024, month=7, day=8
        )

    def test_ny_open_does_not_fire_before_0930_ny_edt(self):
        # 13:25 UTC = 09:25 EDT — before NY open
        assert not _trigger_fires_at(
            self._get_trigger("notify_ny_open"), 13, 25, year=2024, month=7, day=8
        )

    @pytest.mark.parametrize("hour,minute", [
        (14, 0), (14, 5), (14, 30), (15, 0), (15, 55),
    ])
    def test_ny_mid_fires_edt(self, hour, minute):
        # Summer Monday: 10:00–11:55 NY = 14:00–15:55 UTC
        assert _trigger_fires_at(
            self._get_trigger("notify_ny_mid"), hour, minute, year=2024, month=7, day=8
        )

    @pytest.mark.parametrize("hour,minute", [
        (16, 0), (16, 5), (16, 25), (16, 30),
    ])
    def test_ny_close_fires_edt(self, hour, minute):
        # Summer Monday: 12:00–12:30 NY = 16:00–16:30 UTC
        assert _trigger_fires_at(
            self._get_trigger("notify_ny_close"), hour, minute, year=2024, month=7, day=8
        )

    def test_ny_close_does_not_fire_after_1230_ny_edt(self):
        # 16:35 UTC = 12:35 EDT — after session
        assert not _trigger_fires_at(
            self._get_trigger("notify_ny_close"), 16, 35, year=2024, month=7, day=8
        )

    # --- Winter (EST) sanity: NY open = 14:30 UTC ---

    @pytest.mark.parametrize("hour,minute", [
        (14, 30), (14, 35), (14, 55),
    ])
    def test_ny_open_fires_est(self, hour, minute):
        # Winter Monday (EST = UTC-5): 09:30–09:55 NY = 14:30–14:55 UTC
        assert _trigger_fires_at(
            self._get_trigger("notify_ny_open"), hour, minute, year=2024, month=1, day=8
        )

    def test_ny_open_does_not_fire_at_1330_utc_in_winter(self):
        # 13:30 UTC = 08:30 EST — one hour before NY open in winter
        assert not _trigger_fires_at(
            self._get_trigger("notify_ny_open"), 13, 30, year=2024, month=1, day=8
        )

    @pytest.mark.parametrize("hour,minute", [
        (15, 0), (15, 5), (15, 30), (16, 0), (16, 55),
    ])
    def test_ny_mid_fires_est(self, hour, minute):
        # Winter Monday: 10:00–11:55 NY = 15:00–16:55 UTC
        assert _trigger_fires_at(
            self._get_trigger("notify_ny_mid"), hour, minute, year=2024, month=1, day=8
        )

    @pytest.mark.parametrize("hour,minute", [
        (17, 0), (17, 5), (17, 25), (17, 30),
    ])
    def test_ny_close_fires_est(self, hour, minute):
        # Winter Monday: 12:00–12:30 NY = 17:00–17:30 UTC
        assert _trigger_fires_at(
            self._get_trigger("notify_ny_close"), hour, minute, year=2024, month=1, day=8
        )

    def test_ny_close_does_not_fire_after_1230_ny_est(self):
        # 17:35 UTC = 12:35 EST — after session
        assert not _trigger_fires_at(
            self._get_trigger("notify_ny_close"), 17, 35, year=2024, month=1, day=8
        )
