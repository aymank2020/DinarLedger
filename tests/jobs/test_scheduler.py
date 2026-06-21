"""Tests for the tick-based scheduler."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from dinarledger.jobs.scheduler import Scheduler, ScheduledJob


class TestScheduledJob:
    def test_creation(self) -> None:
        job = ScheduledJob(
            job_id="test",
            interval=timedelta(hours=1),
            last_run=None,
            job_func=lambda t: "ok",
        )
        assert job.job_id == "test"
        assert job.last_run is None

    def test_last_run_updated(self) -> None:
        job = ScheduledJob(
            job_id="test",
            interval=timedelta(hours=1),
            last_run=None,
            job_func=lambda t: "ok",
        )
        now = datetime(2025, 1, 1, 12, 0)
        job.last_run = now
        assert job.last_run == now


class TestSchedulerRegister:
    def test_register_single_job(self) -> None:
        sched = Scheduler()
        sched.register("job-a", timedelta(hours=1), lambda t: None)
        assert "job-a" in sched.registered_jobs

    def test_register_duplicate_raises(self) -> None:
        sched = Scheduler()
        sched.register("job-a", timedelta(hours=1), lambda t: None)
        with pytest.raises(ValueError, match="already registered"):
            sched.register("job-a", timedelta(hours=2), lambda t: None)


class TestSchedulerTick:
    def test_tick_runs_due_job(self) -> None:
        results: list[str] = []

        def my_job(t: datetime) -> str:
            results.append("ran")
            return "done"

        sched = Scheduler()
        sched.register("job-a", timedelta(hours=1), my_job)

        out = sched.tick(datetime(2025, 1, 1, 0, 0))
        assert len(out) == 1
        assert out[0] == ("job-a", "done")
        assert results == ["ran"]

    def test_tick_skips_not_due_job(self) -> None:
        sched = Scheduler()
        sched.register("job-a", timedelta(hours=1), lambda t: "ok")

        t1 = datetime(2025, 1, 1, 0, 0)
        sched.tick(t1)

        # Not enough time has passed — should skip
        t2 = datetime(2025, 1, 1, 0, 30)
        out = sched.tick(t2)
        assert len(out) == 0

    def test_tick_runs_again_after_interval(self) -> None:
        call_count = 0

        def counter(t: datetime) -> int:
            nonlocal call_count
            call_count += 1
            return call_count

        sched = Scheduler()
        sched.register("job-a", timedelta(hours=1), counter)

        t1 = datetime(2025, 1, 1, 0, 0)
        sched.tick(t1)

        t2 = datetime(2025, 1, 1, 1, 0)
        out = sched.tick(t2)
        assert len(out) == 1
        assert out[0] == ("job-a", 2)

    def test_multiple_jobs(self) -> None:
        sched = Scheduler()
        sched.register("fast", timedelta(minutes=5), lambda t: "fast")
        sched.register("slow", timedelta(hours=24), lambda t: "slow")

        t1 = datetime(2025, 1, 1, 0, 0)
        out1 = sched.tick(t1)
        assert len(out1) == 2

        t2 = datetime(2025, 1, 1, 0, 10)
        out2 = sched.tick(t2)
        assert len(out2) == 1
        assert out2[0][0] == "fast"


class TestSchedulerNextRun:
    def test_next_run_none_before_first_run(self) -> None:
        sched = Scheduler()
        sched.register("job-a", timedelta(hours=1), lambda t: None)
        assert sched.next_run("job-a") is None

    def test_next_run_after_first_tick(self) -> None:
        sched = Scheduler()
        sched.register("job-a", timedelta(hours=1), lambda t: None)
        t1 = datetime(2025, 1, 1, 0, 0)
        sched.tick(t1)
        assert sched.next_run("job-a") == datetime(2025, 1, 1, 1, 0)

    def test_next_run_unknown_job(self) -> None:
        sched = Scheduler()
        assert sched.next_run("nonexistent") is None


class TestSchedulerCancel:
    def test_cancel_removes_job(self) -> None:
        sched = Scheduler()
        sched.register("job-a", timedelta(hours=1), lambda t: None)
        sched.cancel("job-a")
        assert "job-a" not in sched.registered_jobs

    def test_cancel_unknown_raises(self) -> None:
        sched = Scheduler()
        with pytest.raises(KeyError):
            sched.cancel("nonexistent")


class TestSchedulerIsDue:
    def test_is_due_initially(self) -> None:
        sched = Scheduler()
        sched.register("job-a", timedelta(hours=1), lambda t: None)
        assert sched.is_due("job-a", datetime(2025, 1, 1, 0, 0)) is True

    def test_not_due_after_run(self) -> None:
        sched = Scheduler()
        sched.register("job-a", timedelta(hours=1), lambda t: None)
        sched.tick(datetime(2025, 1, 1, 0, 0))
        assert sched.is_due("job-a", datetime(2025, 1, 1, 0, 30)) is False

    def test_due_again_after_interval(self) -> None:
        sched = Scheduler()
        sched.register("job-a", timedelta(hours=1), lambda t: None)
        sched.tick(datetime(2025, 1, 1, 0, 0))
        assert sched.is_due("job-a", datetime(2025, 1, 1, 1, 0)) is True
