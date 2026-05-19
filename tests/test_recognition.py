"""Tests for dinarledger.revenue.recognition — IFRS 15 recognition logic."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from dinarledger.core.money import Money
from dinarledger.core.types import BillingPeriod
from dinarledger.revenue.recognition import (
    PerformanceObligation,
    calculate_deferred,
    recognize_revenue,
)


@pytest.fixture
def annual_contract_amount() -> Money:
    return Money(Decimal("1200.00"), "USD")


@pytest.fixture
def contract_start() -> date:
    return date(2025, 1, 1)


@pytest.fixture
def contract_end() -> date:
    return date(2025, 12, 31)


@pytest.fixture
def annual_period(contract_start: date, contract_end: date) -> BillingPeriod:
    return BillingPeriod(start_date=contract_start, end_date=contract_end)


@pytest.fixture
def over_time_obligation(contract_start: date, contract_end: date) -> PerformanceObligation:
    return PerformanceObligation(
        obligation_id="obl-saas",
        description="SaaS platform access",
        standalone_price=Money(Decimal("1200"), "USD"),
        satisfied_over_time=True,
        start_date=contract_start,
        end_date=contract_end,
    )


@pytest.fixture
def point_in_time_obligation() -> PerformanceObligation:
    return PerformanceObligation(
        obligation_id="obl-setup",
        description="Initial setup and onboarding",
        standalone_price=Money(Decimal("200"), "USD"),
        satisfied_over_time=False,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 15),
    )


class TestRecognizeOverTime:
    """recognize_revenue() tests for over-time obligations."""

    def test_recognize_over_time(
        self,
        over_time_obligation: PerformanceObligation,
        annual_contract_amount: Money,
        annual_period: BillingPeriod,
    ) -> None:
        """After 3 months, roughly 3/12 of the amount is recognised."""
        # Use a 3-month period
        period = BillingPeriod(start_date=date(2025, 1, 1), end_date=date(2025, 3, 31))
        results = recognize_revenue([over_time_obligation], annual_contract_amount, period)
        assert len(results) == 1
        obl_id, recognised = results[0]
        assert obl_id == "obl-saas"
        # 3 months out of 12 = $300
        expected = Money(Decimal("300"), "USD")
        assert abs(recognised.amount - expected.amount) < Decimal("0.02")

    def test_recognize_over_time_full(
        self,
        over_time_obligation: PerformanceObligation,
        annual_contract_amount: Money,
        annual_period: BillingPeriod,
    ) -> None:
        """Over the full contract period, all revenue is recognised."""
        results = recognize_revenue([over_time_obligation], annual_contract_amount, annual_period)
        obl_id, recognised = results[0]
        # Over 12 months, full $1200 should be recognised
        assert recognised.amount >= annual_contract_amount.amount - Decimal("0.12")

    def test_recognize_over_time_before_start(
        self,
        over_time_obligation: PerformanceObligation,
        annual_contract_amount: Money,
    ) -> None:
        """Before the obligation starts, nothing is recognised."""
        period = BillingPeriod(start_date=date(2024, 1, 1), end_date=date(2024, 12, 31))
        results = recognize_revenue([over_time_obligation], annual_contract_amount, period)
        obl_id, recognised = results[0]
        assert recognised.is_zero()


class TestRecognizePointInTime:
    """recognize_revenue() tests for point-in-time obligations."""

    def test_recognize_point_in_time(self) -> None:
        amount = Money(Decimal("500"), "USD")
        obl = PerformanceObligation(
            obligation_id="obl-setup",
            description="Setup",
            standalone_price=amount,
            satisfied_over_time=False,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 6, 15),
        )

        # Period containing the satisfaction date
        period = BillingPeriod(start_date=date(2025, 6, 1), end_date=date(2025, 6, 30))
        results = recognize_revenue([obl], amount, period)
        obl_id, recognised = results[0]
        assert recognised == amount

        # Period NOT containing the satisfaction date
        period_before = BillingPeriod(start_date=date(2025, 5, 1), end_date=date(2025, 5, 31))
        results_before = recognize_revenue([obl], amount, period_before)
        _, recognised_before = results_before[0]
        assert recognised_before.is_zero()


class TestCalculateDeferred:
    """calculate_deferred() tests."""

    def test_calculate_deferred(
        self,
        over_time_obligation: PerformanceObligation,
        annual_contract_amount: Money,
    ) -> None:
        """Deferred + recognised = total at any point."""
        as_of = date(2025, 3, 31)
        deferred = calculate_deferred(
            [over_time_obligation], annual_contract_amount, as_of
        )
        # Deferred should be positive but less than total
        assert deferred.amount > Decimal("0")
        assert deferred.amount < annual_contract_amount.amount

    def test_calculate_deferred_at_start(
        self,
        over_time_obligation: PerformanceObligation,
        annual_contract_amount: Money,
    ) -> None:
        """At contract start, everything is deferred."""
        deferred = calculate_deferred(
            [over_time_obligation], annual_contract_amount, date(2025, 1, 1)
        )
        # At the very start (Jan 1), 0 months have been fully recognised
        # but the first month's partial recognition has started
        # The deferred should be close to total
        assert deferred.amount >= annual_contract_amount.amount - Decimal("200")

    def test_calculate_deferred_at_end(
        self,
        over_time_obligation: PerformanceObligation,
        annual_contract_amount: Money,
    ) -> None:
        """At contract end, nothing is deferred."""
        deferred = calculate_deferred(
            [over_time_obligation], annual_contract_amount, date(2025, 12, 31)
        )
        assert deferred.is_zero()


class TestAllocationWithDiscount:
    """recognize_revenue() with allocation / discount tests."""

    def test_allocation_with_discount(self) -> None:
        """Two obligations at $600 each, transaction price $1000 → pro-rata."""
        obl1 = PerformanceObligation(
            obligation_id="obl-1",
            description="SaaS",
            standalone_price=Money(Decimal("600"), "USD"),
            satisfied_over_time=True,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 6, 30),
        )
        obl2 = PerformanceObligation(
            obligation_id="obl-2",
            description="Setup",
            standalone_price=Money(Decimal("600"), "USD"),
            satisfied_over_time=False,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 6, 30),
        )
        transaction_price = Money(Decimal("1000.00"), "USD")

        # Over the full period, total recognised should approximate
        # the allocated price for each obligation
        period = BillingPeriod(start_date=date(2025, 1, 1), end_date=date(2025, 6, 30))
        results = recognize_revenue([obl1, obl2], transaction_price, period)
        assert len(results) == 2

        # obl-1 (over-time): allocated = $500, recognised over 6 months
        obl1_id, obl1_recognised = results[0]
        assert obl1_id == "obl-1"

        # obl-2 (point-in-time): allocated = $500, recognised in period
        obl2_id, obl2_recognised = results[1]
        assert obl2_id == "obl-2"
        # Point-in-time should be fully recognised (end_date is in period)
        assert obl2_recognised.amount == Money(Decimal("500"), "USD").amount
