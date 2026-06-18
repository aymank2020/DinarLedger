"""Tests for ReportService — MRR, aging, waterfall, ledger, revenue by period."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from dinarledger.core.enums import InvoiceStatus, SubscriptionStatus
from dinarledger.core.money import Money
from dinarledger.core.types import (
    BillingPeriod,
    Invoice,
    LineItem,
    Payment,
    PaymentStatus,
    Plan,
    Subscription,
)
from dinarledger.revenue.recognition import PerformanceObligation
from dinarledger.services.report_service import ReportService
from dinarledger.customers.ledger import ledger_entry


@pytest.fixture
def svc() -> ReportService:
    return ReportService()


@pytest.fixture
def usd() -> str:
    return "USD"


@pytest.fixture
def monthly_plan(usd: str) -> Plan:
    return Plan(
        plan_id="plan-m",
        name="Pro Monthly",
        base_price=Money(Decimal("99"), usd),
        billing_cycle="monthly",
        trial_days=0,
    )


@pytest.fixture
def active_sub(monthly_plan: Plan) -> Subscription:
    return Subscription(
        sub_id="s1",
        customer_id="c1",
        plan=monthly_plan,
        status=SubscriptionStatus.ACTIVE,
        start_date=date(2025, 3, 1),
        end_date=date(2025, 3, 31),
        seat_count=1,
    )


@pytest.fixture
def plans(monthly_plan: Plan) -> dict[str, Plan]:
    return {monthly_plan.plan_id: monthly_plan}


# ── MRR breakdown ───────────────────────────────────────────────────────────

class TestMRRBreakdown:
    def test_single_active_sub(
        self,
        svc: ReportService,
        active_sub: Subscription,
        plans: dict[str, Plan],
    ) -> None:
        breakdown = svc.mrr_breakdown([active_sub], plans, month=date(2025, 3, 1))
        assert breakdown.total_mrr == Money(Decimal("99"), "USD")

    def test_no_subscriptions(
        self,
        svc: ReportService,
        plans: dict[str, Plan],
    ) -> None:
        breakdown = svc.mrr_breakdown([], plans, month=date(2025, 3, 1))
        assert breakdown.total_mrr.is_zero()

    def test_new_mrr(
        self,
        svc: ReportService,
        active_sub: Subscription,
        plans: dict[str, Plan],
    ) -> None:
        breakdown = svc.mrr_breakdown([active_sub], plans, month=date(2025, 3, 1))
        assert breakdown.new_mrr == Money(Decimal("99"), "USD")

    def test_churn_mrr(
        self,
        svc: ReportService,
        monthly_plan: Plan,
        plans: dict[str, Plan],
    ) -> None:
        cancelled = Subscription(
            sub_id="s2",
            customer_id="c2",
            plan=monthly_plan,
            status=SubscriptionStatus.CANCELLED,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 2, 28),
            cancelled_at=date(2025, 3, 5),
        )
        breakdown = svc.mrr_breakdown([cancelled], plans, month=date(2025, 3, 1))
        assert breakdown.churn_mrr == Money(Decimal("99"), "USD")


# ── Aging summary ───────────────────────────────────────────────────────────

class TestAgingSummary:
    def test_aging_with_overdue_invoice(self, svc: ReportService) -> None:
        invoices = [
            Invoice(
                invoice_id="inv-1",
                customer_id="c1",
                issue_date=date(2025, 1, 1),
                due_date=date(2025, 2, 1),
                line_items=[LineItem(description="X", amount=Money(Decimal("100"), "USD"))],
                status=InvoiceStatus.OVERDUE,
            ),
        ]
        buckets = svc.aging_summary(invoices, as_of=date(2025, 3, 15))
        assert len(buckets) == 5
        # The overdue invoice should appear in one of the buckets
        assert sum(b.invoice_count for b in buckets) == 1

    def test_aging_excludes_paid(self, svc: ReportService) -> None:
        invoices = [
            Invoice(
                invoice_id="inv-paid",
                customer_id="c1",
                issue_date=date(2025, 1, 1),
                due_date=date(2025, 2, 1),
                line_items=[LineItem(description="X", amount=Money(Decimal("100"), "USD"))],
                status=InvoiceStatus.PAID,
            ),
        ]
        buckets = svc.aging_summary(invoices, as_of=date(2025, 3, 15))
        assert all(b.invoice_count == 0 for b in buckets)


# ── Deferred waterfall ──────────────────────────────────────────────────────

class TestDeferredWaterfall:
    def test_waterfall_with_obligations(
        self,
        svc: ReportService,
        usd: str,
    ) -> None:
        obs = [
            PerformanceObligation(
                obligation_id="svc",
                description="Service",
                standalone_price=Money(Decimal("1200"), usd),
                satisfied_over_time=True,
                start_date=date(2025, 1, 1),
                end_date=date(2025, 12, 31),
            ),
        ]
        price = Money(Decimal("1200"), usd)
        entries = svc.deferred_waterfall(obs, price, start=date(2025, 1, 1), end=date(2025, 12, 31))
        assert len(entries) > 0
        assert entries[0].additions == price

    def test_empty_obligations(self, svc: ReportService) -> None:
        entries = svc.deferred_waterfall([], Money(Decimal("0"), "USD"), start=date(2025, 1, 1), end=date(2025, 3, 31))
        assert entries == []


# ── Customer ledger ─────────────────────────────────────────────────────────

class TestCustomerLedger:
    def test_ledger_with_invoices_and_payments(
        self,
        svc: ReportService,
    ) -> None:
        invoices = [
            Invoice(
                invoice_id="inv-1",
                customer_id="c1",
                issue_date=date(2025, 1, 1),
                due_date=date(2025, 1, 31),
                line_items=[LineItem(description="Charge", amount=Money(Decimal("200"), "USD"))],
                status=InvoiceStatus.OPEN,
            ),
        ]
        payments = [
            Payment(
                payment_id="pay-1",
                invoice_id="inv-1",
                amount=Money(Decimal("200"), "USD"),
                status=PaymentStatus.COMPLETED,
                paid_date=date(2025, 1, 15),
            ),
        ]

        result = svc.customer_ledger("c1", invoices, payments)
        assert len(result["entries"]) == 2  # one debit + one credit
        assert result["balance"].is_zero()

    def test_ledger_filters_other_customers(
        self,
        svc: ReportService,
    ) -> None:
        invoices = [
            Invoice(
                invoice_id="inv-1",
                customer_id="c1",
                issue_date=date(2025, 1, 1),
                due_date=date(2025, 1, 31),
                line_items=[LineItem(description="Charge", amount=Money(Decimal("200"), "USD"))],
                status=InvoiceStatus.OPEN,
            ),
            Invoice(
                invoice_id="inv-2",
                customer_id="c2",
                issue_date=date(2025, 1, 1),
                due_date=date(2025, 1, 31),
                line_items=[LineItem(description="Charge", amount=Money(Decimal("300"), "USD"))],
                status=InvoiceStatus.OPEN,
            ),
        ]
        result = svc.customer_ledger("c1", invoices, [])
        assert len(result["entries"]) == 1

    def test_ledger_empty(self, svc: ReportService) -> None:
        result = svc.customer_ledger("c1", [], [])
        assert result["balance"].is_zero()
        assert result["entries"] == []


# ── Revenue by period ───────────────────────────────────────────────────────

class TestRevenueByPeriod:
    def test_multi_period_recognition(
        self,
        svc: ReportService,
        usd: str,
    ) -> None:
        obs = [
            PerformanceObligation(
                obligation_id="svc",
                description="Service",
                standalone_price=Money(Decimal("600"), usd),
                satisfied_over_time=True,
                start_date=date(2025, 1, 1),
                end_date=date(2025, 6, 30),
            ),
        ]
        price = Money(Decimal("600"), usd)
        periods = [
            BillingPeriod(start_date=date(2025, 1, 1), end_date=date(2025, 1, 31)),
            BillingPeriod(start_date=date(2025, 2, 1), end_date=date(2025, 2, 28)),
        ]
        results = svc.revenue_by_period(obs, price, periods)
        assert len(results) == 2
        # Each period should have recognised some revenue
        for period, recognised in results:
            from dinarledger.core.money import sum_money
            total = sum_money(a for _, a in recognised)
            assert total.amount > Decimal("0")

    def test_empty_periods(self, svc: ReportService) -> None:
        results = svc.revenue_by_period([], Money(Decimal("0"), "USD"), [])
        assert results == []
