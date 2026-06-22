"""Tests for the FX rate update job."""

from __future__ import annotations

from datetime import datetime, date
from decimal import Decimal

import pytest

from dinarledger.fx.rates import FXRate
from dinarledger.jobs.fx_job import FXRateJob, FXRateUpdateSummary


def _sample_source(t: datetime) -> list[FXRate]:
    """Deterministic rate source for testing."""
    return [
        FXRate(base="USD", quote="EUR", rate=Decimal("0.92"), rate_date=t.date()),
        FXRate(base="USD", quote="EGP", rate=Decimal("48.50"), rate_date=t.date()),
    ]


class TestFXRateJob:
    def test_no_source_returns_empty(self) -> None:
        job = FXRateJob()
        now = datetime(2025, 1, 15, 0, 0)
        summary = job.run(now)
        assert summary.rates_updated == 0
        assert summary.pairs == []

    def test_source_provides_rates(self) -> None:
        job = FXRateJob(rate_source=_sample_source)
        now = datetime(2025, 1, 15, 0, 0)
        summary = job.run(now)
        assert summary.rates_updated == 2
        assert "USD/EUR" in summary.pairs
        assert "USD/EGP" in summary.pairs

    def test_latest_rates_stored(self) -> None:
        job = FXRateJob(rate_source=_sample_source)
        now = datetime(2025, 1, 15, 0, 0)
        job.run(now)
        rates = job.latest_rates
        assert "USD/EUR" in rates
        assert rates["USD/EUR"].rate == Decimal("0.92")
        assert "USD/EGP" in rates
        assert rates["USD/EGP"].rate == Decimal("48.50")

    def test_rates_overwritten_on_rerun(self) -> None:
        call_count = 0

        def changing_source(t: datetime) -> list[FXRate]:
            nonlocal call_count
            call_count += 1
            rate = Decimal("0.90") + Decimal(str(call_count)) * Decimal("0.01")
            return [
                FXRate(base="USD", quote="EUR", rate=rate, rate_date=t.date()),
            ]

        job = FXRateJob(rate_source=changing_source)
        t1 = datetime(2025, 1, 15, 0, 0)
        job.run(t1)
        assert job.latest_rates["USD/EUR"].rate == Decimal("0.91")

        t2 = datetime(2025, 1, 16, 0, 0)
        job.run(t2)
        assert job.latest_rates["USD/EUR"].rate == Decimal("0.92")

    def test_source_exception_returns_empty(self) -> None:
        def bad_source(t: datetime) -> list[FXRate]:
            raise RuntimeError("API unavailable")

        job = FXRateJob(rate_source=bad_source)
        now = datetime(2025, 1, 15, 0, 0)
        summary = job.run(now)
        assert summary.rates_updated == 0

    def test_callable_interface(self) -> None:
        job = FXRateJob(rate_source=_sample_source)
        now = datetime(2025, 1, 15, 0, 0)
        result = job(now)
        assert isinstance(result, FXRateUpdateSummary)
        assert result.rates_updated == 2
