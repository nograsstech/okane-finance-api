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


def _trigger_fires_at(trigger: CronTrigger, hour: int, minute: int) -> bool:
    """
    Return True if the trigger would fire at the given UTC hour:minute on a
    Monday (weekday=0, always a trading day).
    """
    from datetime import datetime, timezone

    # Monday 2024-01-08 is a known Monday
    dt = datetime(2024, 1, 8, hour, minute, 0, tzinfo=timezone.utc)
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
    """NY session jobs should collectively fire every 5 min 13:30–16:30 UTC."""

    def _get_trigger(self, job_id: str) -> CronTrigger:
        return build_scheduler().get_job(job_id).trigger

    @pytest.mark.parametrize("hour,minute", [
        (13, 30), (13, 35), (13, 55),
    ])
    def test_ny_open_fires(self, hour, minute):
        assert _trigger_fires_at(self._get_trigger("notify_ny_open"), hour, minute)

    def test_ny_open_does_not_fire_before_1330(self):
        assert not _trigger_fires_at(self._get_trigger("notify_ny_open"), 13, 25)

    @pytest.mark.parametrize("hour,minute", [
        (14, 0), (14, 5), (14, 30), (15, 0), (15, 55),
    ])
    def test_ny_mid_fires(self, hour, minute):
        assert _trigger_fires_at(self._get_trigger("notify_ny_mid"), hour, minute)

    @pytest.mark.parametrize("hour,minute", [
        (16, 0), (16, 5), (16, 25), (16, 30),
    ])
    def test_ny_close_fires(self, hour, minute):
        assert _trigger_fires_at(self._get_trigger("notify_ny_close"), hour, minute)

    def test_ny_close_does_not_fire_after_1630(self):
        assert not _trigger_fires_at(self._get_trigger("notify_ny_close"), 16, 35)
