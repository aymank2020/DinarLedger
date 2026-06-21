"""Tick-based job scheduler.

A lightweight scheduler that advances time manually via :meth:`Scheduler.tick`.
Jobs are registered with an interval and a callable; they execute when the
injected ``current_time`` has reached or passed ``last_run + interval``.

This design avoids real-time dependencies, making it straightforward to
test billing cycles that span months in a single test function.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable


@dataclass
class ScheduledJob:
    """A registered job with its scheduling parameters.

    Attributes:
        job_id: Unique identifier for the job.
        interval: Minimum time between successive runs.
        last_run: Timestamp of the most recent execution (``None`` if never).
        job_func: Callable invoked when the job is due.  Receives
            ``current_time`` as its only argument.
    """

    job_id: str
    interval: timedelta
    last_run: datetime | None
    job_func: Callable[[datetime], Any]


class Scheduler:
    """Tick-based scheduler — time is injected, never read from the wall clock.

    Usage::

        scheduler = Scheduler()
        scheduler.register("billing", timedelta(days=30), run_billing)
        scheduler.tick(datetime(2025, 2, 1))   # runs billing if due
    """

    def __init__(self) -> None:
        self._jobs: dict[str, ScheduledJob] = {}

    # ── Registration ─────────────────────────────────────────────────────

    def register(
        self,
        job_id: str,
        interval: timedelta,
        job_func: Callable[[datetime], Any],
    ) -> None:
        """Register a new job.

        Raises :class:`ValueError` if *job_id* is already registered.
        """
        if job_id in self._jobs:
            raise ValueError(f"Job '{job_id}' is already registered")
        self._jobs[job_id] = ScheduledJob(
            job_id=job_id,
            interval=interval,
            last_run=None,
            job_func=job_func,
        )

    # ── Execution ────────────────────────────────────────────────────────

    def tick(self, current_time: datetime) -> list[tuple[str, Any]]:
        """Run all due jobs at *current_time*.

        A job is due when it has never run, or when
        ``current_time >= last_run + interval``.

        Returns a list of ``(job_id, result)`` tuples for every job that
        was executed (in registration order).
        """
        results: list[tuple[str, Any]] = []

        for job in self._jobs.values():
            if self._is_due(job, current_time):
                result = job.job_func(current_time)
                job.last_run = current_time
                results.append((job.job_id, result))

        return results

    # ── Queries ──────────────────────────────────────────────────────────

    def next_run(self, job_id: str) -> datetime | None:
        """Return the next scheduled run time for *job_id*.

        Returns ``None`` if the job has never run (it will run on the
        next tick) or if the job is not registered.
        """
        job = self._jobs.get(job_id)
        if job is None:
            return None
        if job.last_run is None:
            return None
        return job.last_run + job.interval

    def is_due(self, job_id: str, current_time: datetime) -> bool:
        """Check whether *job_id* is due at *current_time*."""
        job = self._jobs.get(job_id)
        if job is None:
            return False
        return self._is_due(job, current_time)

    # ── Cancellation ─────────────────────────────────────────────────────

    def cancel(self, job_id: str) -> None:
        """Remove a registered job.

        Raises :class:`KeyError` if *job_id* is not found.
        """
        if job_id not in self._jobs:
            raise KeyError(f"Job '{job_id}' is not registered")
        del self._jobs[job_id]

    # ── Introspection ────────────────────────────────────────────────────

    @property
    def registered_jobs(self) -> list[str]:
        """List of registered job IDs."""
        return list(self._jobs.keys())

    # ── Internal ─────────────────────────────────────────────────────────

    @staticmethod
    def _is_due(job: ScheduledJob, current_time: datetime) -> bool:
        if job.last_run is None:
            return True
        return current_time >= job.last_run + job.interval
