"""Tests for the revenue recognition job."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest

from dinarledger.core.money import Money
from dinarledger.core.types import BillingPeriod
from dinarledger.revenue.recognition import PerformanceObligation
from dinarledger.jobs.revenue_job import RevenueJob, RevenueRunSummary


class TestRevenueJob:
    def test_empty_obligations_returns_zero(self) -> None:
        job = RevenueJob()
        now = datetime(2025, 1, 1)
        summary = job.run(now)
        assert summary.obligations_processed == 0
        assert summary.total_recognized.is_zero()

    def test_recognizes_over_time_obligation(self) -> None:
        obligations = [
            PerformanceObligation(
                obligation_id="saas",
                description="SaaS",
                standalone_price=Money(Decimal("1200.00"), "USD"),
                satisfied_over_time=True,
                start_date=date(2025, 1, 1),
                end_date=date(2025, 12, 31),
            ),
        ]
        period = BillingPeriod(start_date=date(2025, 1, 1), end_date=date(2025, 1, 31))
        job = RevenueJob(
            obligations=obligations,
            transaction_price=Money(Decimal("1200.00"), "USD"),
            period=period,
        )

        now = datetime(2025, 1, 31)
        summary = job.run(now)
        assert summary.obligations_processed == 1
        assert summary.total_recognized.amount > Decimal("0")

    def test_point_in_time_not_yet_satisfied(self) -> None:
        obligations = [
            PerformanceObligation(
                obligation_id="setup",
                description="Setup",
                standalone_price=Money(Decimal("500.00"), "USD"),
                satisfied_over_time=False,
                start_date=date(2025, 1, 1),
                end_date=date(2025, 3, 31),
            ),
        ]
        period = BillingPeriod(start_date=date(2025, 1, 1), end_date=date(2025, 1, 31))
        job = RevenueJob(
            obligations=obligations,
            transaction_price=Money(Decimal("500.00"), "USD"),
            period=period,
        )

        now = datetime(2025, 1, 31)
        summary = job.run(now)
        assert summary.total_recognized.is_zero()
        assert summary.zero_recognized_count == 1

    def test_configure_and_call(self) -> None:
        job = RevenueJob()
        now = datetime(2025, 1, 31)
        summary_before = job.run(now)
        assert summary_before.obligations_processed == 0

        obligations = [
            PerformanceObligation(
                obligation_id="svc",
                description="Service",
                standalone_price=Money(Decimal("600.00"), "USD"),
                satisfied_over_time=True,
                start_date=date(2025, 1, 1),
                end_date=date(2025, 12, 31),
            ),
        ]
        period = BillingPeriod(start_date=date(2025, 1, 1), end_date=date(2025, 1, 31))
        job.configure(obligations, Money(Decimal("600.00"), "USD"), period)
        summary_after = job.run(now)
        assert summary_after.obligations_processed == 1

    def test_callable_interface(self) -> None:
        obligations = [
            PerformanceObligation(
                obligation_id="saas",
                description="SaaS",
                standalone_price=Money(Decimal("1200.00"), "USD"),
                satisfied_over_time=True,
                start_date=date(2025, 1, 1),
                end_date=date(2025, 12, 31),
            ),
        ]
        period = BillingPeriod(start_date=date(2025, 1, 1), end_date=date(2025, 1, 31))
        job = RevenueJob(
            obligations=obligations,
            transaction_price=Money(Decimal("1200.00"), "USD"),
            period=period,
        )
        now = datetime(2025, 1, 31)
        result = job(now)
        assert isinstance(result, RevenueRunSummary)
