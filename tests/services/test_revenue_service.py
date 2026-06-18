"""Tests for RevenueService — recognition, deferred summary,
waterfall schedule, bundle allocation."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from dinarledger.core.money import Money, sum_money
from dinarledger.core.types import BillingPeriod
from dinarledger.revenue.recognition import PerformanceObligation
from dinarledger.services.revenue_service import RevenueService


@pytest.fixture
def svc() -> RevenueService:
    return RevenueService()


@pytest.fixture
def usd() -> str:
    return "USD"


@pytest.fixture
def obligations_12mo(usd: str) -> list[PerformanceObligation]:
    """Two obligations over a 12-month period."""
    return [
        PerformanceObligation(
            obligation_id="svc-platform",
            description="Platform access",
            standalone_price=Money(Decimal("1200"), usd),
            satisfied_over_time=True,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
        ),
        PerformanceObligation(
            obligation_id="svc-onboarding",
            description="Onboarding service",
            standalone_price=Money(Decimal("300"), usd),
            satisfied_over_time=False,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 2, 28),
        ),
    ]


@pytest.fixture
def transaction_price(usd: str) -> Money:
    return Money(Decimal("1500"), usd)


# ── Recognition ─────────────────────────────────────────────────────────────

class TestRecognizePeriod:
    def test_recognize_first_month(
        self,
        svc: RevenueService,
        obligations_12mo: list[PerformanceObligation],
        transaction_price: Money,
    ) -> None:
        period = BillingPeriod(start_date=date(2025, 1, 1), end_date=date(2025, 1, 31))
        results = svc.recognize_period(obligations_12mo, transaction_price, period)
        result_map = dict(results)
        # Platform should recognise ~1/12 of allocated price
        assert result_map["svc-platform"].amount > Decimal("0")
        # Onboarding is point-in-time, end_date is Feb 28, not in Jan
        assert result_map["svc-onboarding"].is_zero()

    def test_recognize_point_in_time_obligation(
        self,
        svc: RevenueService,
        obligations_12mo: list[PerformanceObligation],
        transaction_price: Money,
    ) -> None:
        period = BillingPeriod(start_date=date(2025, 2, 1), end_date=date(2025, 2, 28))
        results = svc.recognize_period(obligations_12mo, transaction_price, period)
        result_map = dict(results)
        # Onboarding ends in Feb, so should be fully recognised
        assert result_map["svc-onboarding"].amount > Decimal("0")

    def test_empty_obligations(self, svc: RevenueService) -> None:
        period = BillingPeriod(start_date=date(2025, 1, 1), end_date=date(2025, 1, 31))
        results = svc.recognize_period([], Money(Decimal("0"), "USD"), period)
        assert results == []


# ── Deferred summary ────────────────────────────────────────────────────────

class TestDeferredSummary:
    def test_deferred_before_recognition(
        self,
        svc: RevenueService,
        obligations_12mo: list[PerformanceObligation],
        transaction_price: Money,
    ) -> None:
        # Before any recognition — full price is deferred
        deferred = svc.deferred_summary(obligations_12mo, transaction_price, as_of=date(2024, 12, 31))
        assert deferred.amount == transaction_price.amount

    def test_deferred_mid_contract(
        self,
        svc: RevenueService,
        obligations_12mo: list[PerformanceObligation],
        transaction_price: Money,
    ) -> None:
        # Mid-contract: some revenue recognised, some still deferred
        deferred = svc.deferred_summary(obligations_12mo, transaction_price, as_of=date(2025, 6, 30))
        assert Decimal("0") < deferred.amount < transaction_price.amount

    def test_deferred_after_completion(
        self,
        svc: RevenueService,
        obligations_12mo: list[PerformanceObligation],
        transaction_price: Money,
    ) -> None:
        # After all obligations completed — zero deferred
        deferred = svc.deferred_summary(obligations_12mo, transaction_price, as_of=date(2026, 1, 1))
        assert deferred.is_zero()


# ── Waterfall schedule ──────────────────────────────────────────────────────

class TestWaterfallSchedule:
    def test_waterfall_produces_entries(
        self,
        svc: RevenueService,
        obligations_12mo: list[PerformanceObligation],
        transaction_price: Money,
    ) -> None:
        entries = svc.waterfall_schedule(
            obligations_12mo, transaction_price,
            start=date(2025, 1, 1), end=date(2025, 12, 31),
        )
        assert len(entries) > 0
        # First entry: additions should equal transaction price
        assert entries[0].additions == transaction_price
        # Ending of first month = additions - recognised
        assert entries[0].ending_balance.amount > Decimal("0")

    def test_waterfall_ending_goes_to_zero(
        self,
        svc: RevenueService,
        obligations_12mo: list[PerformanceObligation],
        transaction_price: Money,
    ) -> None:
        entries = svc.waterfall_schedule(
            obligations_12mo, transaction_price,
            start=date(2025, 1, 1), end=date(2025, 12, 31),
        )
        # By the end, deferred should be zero (all recognised)
        assert entries[-1].ending_balance.is_zero()


# ── Bundle allocation ───────────────────────────────────────────────────────

class TestBundleAllocation:
    def test_proportional_allocation(
        self,
        svc: RevenueService,
        obligations_12mo: list[PerformanceObligation],
        transaction_price: Money,
    ) -> None:
        allocations = svc.bundle_allocation(
            obligations_12mo, transaction_price, method="proportional"
        )
        assert len(allocations) == 2
        allocated_total = sum_money(a for _, a in allocations)
        # Total allocated should approximately equal transaction price
        assert abs(allocated_total.amount - transaction_price.amount) <= Decimal("0.02")

    def test_residual_allocation(
        self,
        svc: RevenueService,
        usd: str,
    ) -> None:
        # One obligation with known SSP, one with zero SSP
        obs = [
            PerformanceObligation(
                obligation_id="known",
                description="Known price",
                standalone_price=Money(Decimal("800"), usd),
                satisfied_over_time=True,
                start_date=date(2025, 1, 1),
                end_date=date(2025, 6, 30),
            ),
            PerformanceObligation(
                obligation_id="uncertain",
                description="Uncertain price",
                standalone_price=Money(Decimal("0"), usd),
                satisfied_over_time=True,
                start_date=date(2025, 1, 1),
                end_date=date(2025, 6, 30),
            ),
        ]
        total_price = Money(Decimal("1200"), usd)

        allocations = svc.bundle_allocation(obs, total_price, method="residual")
        alloc_map = {o.obligation_id: a for o, a in allocations}
        # Known obligation gets its full SSP
        assert alloc_map["known"].amount == Decimal("800")
        # Uncertain gets the residual
        assert alloc_map["uncertain"].amount == Decimal("400")

    def test_invalid_method_raises(
        self,
        svc: RevenueService,
        obligations_12mo: list[PerformanceObligation],
        transaction_price: Money,
    ) -> None:
        with pytest.raises(ValueError, match="Unknown allocation method"):
            svc.bundle_allocation(obligations_12mo, transaction_price, method="invalid")
