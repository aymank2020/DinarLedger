"""Tests for BillingService — billing cycle, payment processing,
void, credit note, aging report."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from dinarledger.core.enums import InvoiceStatus, SubscriptionStatus
from dinarledger.core.errors import InvoiceError, PaymentAllocationError
from dinarledger.core.money import Money
from dinarledger.core.types import (
    BillingPeriod,
    Invoice,
    LineItem,
    Payment,
    PaymentStatus,
    Plan,
    Subscription,
    TaxRate,
)
from dinarledger.services.billing_service import BillingService
from dinarledger.storage.memory import MemoryRepository


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def invoice_repo() -> MemoryRepository[Invoice]:
    return MemoryRepository(Invoice)


@pytest.fixture
def payment_repo() -> MemoryRepository[Payment]:
    return MemoryRepository(Payment)


@pytest.fixture
def svc(
    invoice_repo: MemoryRepository[Invoice],
    payment_repo: MemoryRepository[Payment],
) -> BillingService:
    return BillingService(invoice_repo, payment_repo)


@pytest.fixture
def monthly_plan() -> Plan:
    return Plan(
        plan_id="plan-m",
        name="Pro Monthly",
        base_price=Money(Decimal("99"), "USD"),
        billing_cycle="monthly",
        trial_days=0,
    )


@pytest.fixture
def tax_rates() -> dict[str, TaxRate]:
    return {
        "standard": TaxRate(
            code="VAT-14", rate=Decimal("0.14"), description="Standard VAT 14%"
        ),
    }


@pytest.fixture
def active_sub(monthly_plan: Plan) -> Subscription:
    return Subscription(
        sub_id="sub-1",
        customer_id="c1",
        plan=monthly_plan,
        status=SubscriptionStatus.ACTIVE,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 31),
        seat_count=1,
    )


@pytest.fixture
def period() -> BillingPeriod:
    return BillingPeriod(start_date=date(2025, 1, 1), end_date=date(2025, 1, 31))


def _make_invoice(
    invoice_id: str = "inv-1",
    customer_id: str = "c1",
    amount: Decimal = Decimal("200"),
    status: InvoiceStatus = InvoiceStatus.OPEN,
    due_date: date = date(2025, 2, 28),
) -> Invoice:
    return Invoice(
        invoice_id=invoice_id,
        customer_id=customer_id,
        issue_date=date(2025, 1, 15),
        due_date=due_date,
        line_items=[LineItem(description="Charge", amount=Money(amount, "USD"))],
        status=status,
    )


# ── Billing cycle ───────────────────────────────────────────────────────────

class TestRunBillingCycle:
    def test_generates_invoices_for_active_subs(
        self,
        svc: BillingService,
        active_sub: Subscription,
        period: BillingPeriod,
        tax_rates: dict[str, TaxRate],
    ) -> None:
        invoices = svc.run_billing_cycle([active_sub], period, tax_rates)
        assert len(invoices) == 1
        assert invoices[0].status == InvoiceStatus.OPEN
        assert invoices[0].customer_id == "c1"

    def test_skips_cancelled_subs(
        self,
        svc: BillingService,
        active_sub: Subscription,
        period: BillingPeriod,
        tax_rates: dict[str, TaxRate],
    ) -> None:
        cancelled = replace(active_sub, status=SubscriptionStatus.CANCELLED)
        invoices = svc.run_billing_cycle([cancelled], period, tax_rates)
        assert invoices == []

    def test_empty_subscriptions(
        self,
        svc: BillingService,
        period: BillingPeriod,
        tax_rates: dict[str, TaxRate],
    ) -> None:
        invoices = svc.run_billing_cycle([], period, tax_rates)
        assert invoices == []

    def test_invoice_includes_tax(
        self,
        svc: BillingService,
        active_sub: Subscription,
        monthly_plan: Plan,
        period: BillingPeriod,
        tax_rates: dict[str, TaxRate],
    ) -> None:
        # Plan with a tax_code so that generate_invoice includes tax lines
        taxable_plan = replace(monthly_plan, tax_code="standard")
        sub = replace(active_sub, plan=taxable_plan)
        invoices = svc.run_billing_cycle(
            [sub], period,
            {"standard": tax_rates["standard"]},
        )
        assert len(invoices) == 1
        tax_items = [li for li in invoices[0].line_items if li.is_tax]
        assert len(tax_items) >= 1


# ── Payment processing ─────────────────────────────────────────────────────

class TestProcessPayment:
    def test_full_payment(
        self,
        svc: BillingService,
        invoice_repo: MemoryRepository[Invoice],
    ) -> None:
        inv = _make_invoice(amount=Decimal("200"))
        invoice_repo.add(inv)

        payment, allocations, unallocated = svc.process_payment(
            "c1", Money(Decimal("200"), "USD"), [inv]
        )
        assert payment.status == PaymentStatus.COMPLETED
        assert unallocated.is_zero()

    def test_partial_payment(
        self,
        svc: BillingService,
        invoice_repo: MemoryRepository[Invoice],
    ) -> None:
        inv = _make_invoice(amount=Decimal("200"))
        invoice_repo.add(inv)

        _, allocations, unallocated = svc.process_payment(
            "c1", Money(Decimal("100"), "USD"), [inv]
        )
        assert unallocated.is_zero()

    def test_overpayment(
        self,
        svc: BillingService,
        invoice_repo: MemoryRepository[Invoice],
    ) -> None:
        inv = _make_invoice(amount=Decimal("100"))
        invoice_repo.add(inv)

        _, _, unallocated = svc.process_payment(
            "c1", Money(Decimal("150"), "USD"), [inv]
        )
        assert unallocated == Money(Decimal("50"), "USD")

    def test_zero_amount_raises(self, svc: BillingService) -> None:
        with pytest.raises(Exception):
            svc.process_payment("c1", Money(Decimal("0"), "USD"), [_make_invoice()])

    def test_no_invoices_raises(self, svc: BillingService) -> None:
        with pytest.raises(PaymentAllocationError):
            svc.process_payment("c1", Money(Decimal("100"), "USD"), [])

    def test_highest_first_strategy(
        self,
        svc: BillingService,
        invoice_repo: MemoryRepository[Invoice],
    ) -> None:
        inv_small = _make_invoice(invoice_id="inv-s", amount=Decimal("50"))
        inv_big = _make_invoice(invoice_id="inv-b", amount=Decimal("200"))
        invoice_repo.add(inv_small)
        invoice_repo.add(inv_big)

        _, allocations, _ = svc.process_payment(
            "c1",
            Money(Decimal("150"), "USD"),
            [inv_small, inv_big],
            strategy="highest_first",
        )
        # Biggest invoice should be allocated first
        alloc_map = dict(allocations)
        assert alloc_map["inv-b"] == Money(Decimal("150"), "USD")
        assert alloc_map["inv-s"] == Money(Decimal("0"), "USD")


# ── Void invoice ────────────────────────────────────────────────────────────

class TestVoidInvoice:
    def test_void_open_invoice(
        self,
        svc: BillingService,
        invoice_repo: MemoryRepository[Invoice],
    ) -> None:
        inv = _make_invoice()
        invoice_repo.add(inv)

        voided = svc.void_invoice("inv-1")
        assert voided.status == InvoiceStatus.VOIDED

    def test_void_paid_invoice_raises(
        self,
        svc: BillingService,
        invoice_repo: MemoryRepository[Invoice],
    ) -> None:
        inv = _make_invoice(status=InvoiceStatus.PAID)
        invoice_repo.add(inv)

        with pytest.raises(InvoiceError, match="PAID"):
            svc.void_invoice("inv-1")

    def test_void_not_found_raises(self, svc: BillingService) -> None:
        with pytest.raises(InvoiceError, match="not found"):
            svc.void_invoice("nonexistent")


# ── Credit note ─────────────────────────────────────────────────────────────

class TestApplyCreditNote:
    def test_credit_note_on_open_invoice(
        self,
        svc: BillingService,
        invoice_repo: MemoryRepository[Invoice],
    ) -> None:
        inv = _make_invoice(amount=Decimal("200"))
        invoice_repo.add(inv)

        adjusted = svc.apply_credit_note("inv-1", Money(Decimal("50"), "USD"))
        credit_items = [li for li in adjusted.line_items if li.item_type == "credit"]
        assert len(credit_items) == 1

    def test_credit_note_on_paid_invoice_raises(
        self,
        svc: BillingService,
        invoice_repo: MemoryRepository[Invoice],
    ) -> None:
        inv = _make_invoice(status=InvoiceStatus.PAID)
        invoice_repo.add(inv)

        with pytest.raises(InvoiceError):
            svc.apply_credit_note("inv-1", Money(Decimal("10"), "USD"))

    def test_credit_note_not_found_raises(self, svc: BillingService) -> None:
        with pytest.raises(InvoiceError, match="not found"):
            svc.apply_credit_note("nonexistent", Money(Decimal("10"), "USD"))


# ── Aging report ────────────────────────────────────────────────────────────

class TestAgingReport:
    def test_aging_buckets(
        self,
        svc: BillingService,
    ) -> None:
        invoices = [
            _make_invoice(due_date=date(2025, 2, 15)),
            _make_invoice(invoice_id="inv-2", due_date=date(2025, 3, 1)),
        ]
        buckets = svc.aging_report(invoices, as_of=date(2025, 3, 15))
        assert len(buckets) == 5  # Current, 1-30, 31-60, 61-90, 90+
        # At least one bucket should have a non-zero total
        assert any(b.invoice_count > 0 for b in buckets)
