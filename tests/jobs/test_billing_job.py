"""Tests for the billing job."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from dinarledger.core.enums import SubscriptionStatus
from dinarledger.core.money import Money
from dinarledger.core.types import (
    BillingPeriod,
    Plan,
    Subscription,
    TaxRate,
)
from dinarledger.jobs.billing_job import BillingJob, BillingRunSummary


def _make_plan(price: Decimal = Decimal("50.00"), cycle: str = "monthly") -> Plan:
    return Plan(
        plan_id="plan-test",
        name="Test Plan",
        base_price=Money(price, "USD"),
        billing_cycle=cycle,
    )


def _make_sub(
    customer_id: str = "cust-001",
    status: SubscriptionStatus = SubscriptionStatus.ACTIVE,
    plan: Plan | None = None,
) -> Subscription:
    return Subscription(
        sub_id="sub-test",
        customer_id=customer_id,
        plan=plan or _make_plan(),
        status=status,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 31),
    )


class TestBillingJob:
    def test_generates_invoice_for_active_sub(self) -> None:
        job = BillingJob()
        sub = _make_sub()
        period = BillingPeriod(start_date=date(2025, 1, 1), end_date=date(2025, 1, 31))
        now = datetime(2025, 1, 1)

        summary = job.run([sub], period, now)
        assert summary.invoices_generated == 1
        assert summary.invoices_skipped == 0
        assert summary.errors == 0
        assert summary.total_amount.amount > Decimal("0")

    def test_skips_inactive_subscriptions(self) -> None:
        job = BillingJob()
        sub = _make_sub(status=SubscriptionStatus.CANCELLED)
        period = BillingPeriod(start_date=date(2025, 1, 1), end_date=date(2025, 1, 31))
        now = datetime(2025, 1, 1)

        summary = job.run([sub], period, now)
        assert summary.invoices_generated == 0
        assert summary.invoices_skipped == 1

    def test_multiple_subscriptions(self) -> None:
        job = BillingJob()
        subs = [
            _make_sub(customer_id=f"cust-{i:03d}")
            for i in range(5)
        ]
        period = BillingPeriod(start_date=date(2025, 1, 1), end_date=date(2025, 1, 31))
        now = datetime(2025, 1, 1)

        summary = job.run(subs, period, now)
        assert summary.invoices_generated == 5

    def test_call_without_configure_returns_empty(self) -> None:
        job = BillingJob()
        now = datetime(2025, 1, 1)
        summary = job(now)
        assert summary.invoices_generated == 0

    def test_configure_and_call(self) -> None:
        job = BillingJob()
        sub = _make_sub()
        period = BillingPeriod(start_date=date(2025, 1, 1), end_date=date(2025, 1, 31))
        job.configure([sub], period)
        now = datetime(2025, 1, 1)
        summary = job(now)
        assert summary.invoices_generated == 1

    def test_with_tax_rates(self) -> None:
        tax_rates = {
            "VAT": TaxRate(code="VAT", rate=Decimal("0.05"), description="Test VAT"),
        }
        job = BillingJob(tax_rates=tax_rates, tax_code="VAT")
        sub = _make_sub()
        period = BillingPeriod(start_date=date(2025, 1, 1), end_date=date(2025, 1, 31))
        now = datetime(2025, 1, 1)

        summary = job.run([sub], period, now)
        assert summary.invoices_generated == 1
        assert summary.total_amount.amount > Decimal("50.00")  # includes tax
