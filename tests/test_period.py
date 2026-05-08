"""Tests for dinarledger.core.period — billing period and proration helpers."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from dinarledger.core.errors import InvalidParameterError
from dinarledger.core.period import (
    BillingPeriod,
    billing_periods,
    days_in_month,
    days_in_period,
    proration_fraction,
    stub_period,
)
from dinarledger.core.types import BillingPeriod as BillingPeriodType


class TestDaysInMonth:
    """days_in_month tests."""

    def test_days_in_month_regular(self) -> None:
        assert days_in_month(2025, 1) == 31
        assert days_in_month(2025, 4) == 30

    def test_days_in_month_february_leap(self) -> None:
        # 2024 is a leap year
        assert days_in_month(2024, 2) == 29
        # 2025 is not
        assert days_in_month(2025, 2) == 28

    def test_days_in_month_invalid_month(self) -> None:
        with pytest.raises(InvalidParameterError):
            days_in_month(2025, 13)


class TestBillingPeriods:
    """billing_periods tests."""

    def test_billing_periods_monthly(self) -> None:
        periods = billing_periods(date(2025, 1, 1), 3, "monthly")
        assert len(periods) == 3
        # Periods are inclusive: Jan 1–31, Feb 1–28 (2025), Mar 1–31
        assert periods[0].start_date == date(2025, 1, 1)
        assert periods[0].end_date == date(2025, 1, 31)
        assert periods[1].start_date == date(2025, 2, 1)
        assert periods[1].end_date == date(2025, 2, 28)
        assert periods[2].start_date == date(2025, 3, 1)
        assert periods[2].end_date == date(2025, 3, 31)

    def test_billing_periods_quarterly(self) -> None:
        periods = billing_periods(date(2025, 1, 1), 2, "quarterly")
        assert len(periods) == 2
        assert periods[0].start_date == date(2025, 1, 1)
        assert periods[0].end_date == date(2025, 3, 31)
        assert periods[1].start_date == date(2025, 4, 1)
        assert periods[1].end_date == date(2025, 6, 30)


class TestProrationFraction:
    """proration_fraction tests."""

    def test_proration_full_period(self) -> None:
        """Using the full period yields a fraction of 1.0."""
        period = BillingPeriodType(date(2025, 1, 1), date(2025, 1, 31))
        frac = proration_fraction(period, date(2025, 1, 1), date(2025, 1, 31))
        assert frac == Decimal("1")

    def test_proration_mid_month(self) -> None:
        """Half-month usage in a 30-day period."""
        period = BillingPeriodType(date(2025, 1, 1), date(2025, 1, 30))
        # Active from Jan 16 to Jan 30 = 15 days (inclusive)
        frac = proration_fraction(period, date(2025, 1, 16), date(2025, 1, 30))
        # 15/30 = 0.5
        assert frac == Decimal("0.5000000000")

    def test_proration_no_overlap(self) -> None:
        """Usage entirely outside the period yields 0."""
        period = BillingPeriodType(date(2025, 1, 1), date(2025, 1, 31))
        frac = proration_fraction(period, date(2025, 2, 1), date(2025, 2, 28))
        assert frac == Decimal("0")


class TestStubPeriod:
    """stub_period tests.

    stub_period returns the remaining portion of a period from the
    effective_date to the period end.
    """

    def test_stub_period(self) -> None:
        period = BillingPeriodType(date(2025, 1, 1), date(2025, 1, 31))
        stub = stub_period(period, date(2025, 1, 15))
        assert stub is not None
        assert stub.start_date == date(2025, 1, 15)
        assert stub.end_date == date(2025, 1, 31)

    def test_stub_period_past_end(self) -> None:
        """Effective date after period end → None."""
        period = BillingPeriodType(date(2025, 1, 1), date(2025, 1, 31))
        stub = stub_period(period, date(2025, 2, 1))
        assert stub is None


class TestDaysInPeriod:
    """days_in_period tests."""

    def test_days_in_period_normal(self) -> None:
        # Jan 1 to Jan 31 = 31 days inclusive
        assert days_in_period(date(2025, 1, 1), date(2025, 1, 31)) == 31

    def test_days_in_period_same_day(self) -> None:
        assert days_in_period(date(2025, 1, 15), date(2025, 1, 15)) == 1

    def test_days_in_period_reversed(self) -> None:
        assert days_in_period(date(2025, 1, 31), date(2025, 1, 1)) == 0
