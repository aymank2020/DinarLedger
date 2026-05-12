"""Tests for dinarledger.billing.invoice_gen — invoice generation and mutations."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from dinarledger.billing.invoice_gen import (
    apply_adjustment,
    generate_invoice,
    void_invoice,
)
from dinarledger.core.enums import InvoiceStatus, LineItemType, SubscriptionStatus
from dinarledger.core.errors import InvoiceError
from dinarledger.core.money import Money
from dinarledger.core.types import (
    BillingPeriod,
    Invoice,
    LineItem,
    Plan,
    Subscription,
    TaxRate,
)


@pytest.fixture
def plan_monthly() -> Plan:
    return Plan(
        plan_id="plan-monthly",
        name="Professional Monthly",
        base_price=Money(Decimal("99"), "USD"),
        billing_cycle="monthly",
        trial_days=14,
    )


@pytest.fixture
def plan_with_setup() -> Plan:
    return Plan(
        plan_id="plan-annual",
        name="Professional Annual",
        base_price=Money(Decimal("999"), "USD"),
        billing_cycle="annual",
        setup_fee=Money(Decimal("99"), "USD"),
        trial_days=0,
    )


@pytest.fixture
def sub_single_seat(plan_monthly: Plan) -> Subscription:
    return Subscription(
        sub_id="sub-001",
        customer_id="cust-001",
        plan=plan_monthly,
        status=SubscriptionStatus.ACTIVE,
        start_date=date(2025, 3, 1),
        end_date=date(2025, 3, 31),
        seat_count=1,
    )


@pytest.fixture
def sub_multi_seat(plan_monthly: Plan) -> Subscription:
    return Subscription(
        sub_id="sub-002",
        customer_id="cust-001",
        plan=plan_monthly,
        status=SubscriptionStatus.ACTIVE,
        start_date=date(2025, 3, 1),
        end_date=date(2025, 3, 31),
        seat_count=5,
    )


@pytest.fixture
def sub_annual(plan_with_setup: Plan) -> Subscription:
    return Subscription(
        sub_id="sub-003",
        customer_id="cust-001",
        plan=plan_with_setup,
        status=SubscriptionStatus.ACTIVE,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
        seat_count=1,
    )


@pytest.fixture
def billing_period() -> BillingPeriod:
    return BillingPeriod(start_date=date(2025, 3, 1), end_date=date(2025, 3, 31))


@pytest.fixture
def tax_rates() -> dict[str, TaxRate]:
    return {
        "": TaxRate(code="VAT-0", rate=Decimal("0"), description="No tax", is_exempt=True),
        "standard": TaxRate(code="VAT-14", rate=Decimal("0.14"), description="Standard VAT"),
    }


class TestGenerateInvoice:
    """generate_invoice() tests."""

    def test_generate_monthly_invoice(
        self, sub_single_seat: Subscription, billing_period: BillingPeriod, tax_rates: dict
    ) -> None:
        inv = generate_invoice(sub_single_seat, billing_period, tax_rates)
        assert inv is not None
        assert inv.status == InvoiceStatus.DRAFT
        assert inv.customer_id == "cust-001"
        # Should have at least the subscription charge line
        assert len(inv.line_items) >= 1
        # Total should include the $99 base price (may also include tax)
        assert inv.subtotal == Money(Decimal("99"), "USD")

    def test_generate_with_setup_fee(
        self, sub_annual: Subscription, tax_rates: dict
    ) -> None:
        period = BillingPeriod(start_date=date(2025, 1, 1), end_date=date(2025, 1, 31))
        inv = generate_invoice(sub_annual, period, tax_rates, is_first_invoice=True)
        assert inv is not None
        # Should have subscription charge + setup fee + possibly tax lines
        non_tax_items = [li for li in inv.line_items if not li.is_tax]
        # At least: subscription charge + setup fee
        assert len(non_tax_items) >= 2

    def test_generate_with_seats(
        self, sub_multi_seat: Subscription, billing_period: BillingPeriod, tax_rates: dict
    ) -> None:
        inv = generate_invoice(sub_multi_seat, billing_period, tax_rates)
        assert inv is not None
        # 5 seats with plan that includes 1 seat → 4 extra seats
        # Base price $99 + overage
        assert inv.subtotal.amount > Money(Decimal("99"), "USD").amount

    def test_generate_not_active_returns_none(self, plan_monthly: Plan) -> None:
        """Only ACTIVE subscriptions generate invoices."""
        sub = Subscription(
            sub_id="sub-inactive",
            customer_id="cust-001",
            plan=plan_monthly,
            status=SubscriptionStatus.CANCELLED,
            start_date=date(2025, 3, 1),
            end_date=date(2025, 3, 31),
        )
        period = BillingPeriod(start_date=date(2025, 3, 1), end_date=date(2025, 3, 31))
        inv = generate_invoice(sub, period, {})
        assert inv is None


class TestApplyAdjustment:
    """apply_adjustment() tests."""

    def test_apply_credit_adjustment(
        self, sub_single_seat: Subscription, billing_period: BillingPeriod, tax_rates: dict
    ) -> None:
        inv = generate_invoice(sub_single_seat, billing_period, tax_rates)
        assert inv is not None
        original_total = inv.total

        credit = LineItem(
            description="Goodwill credit",
            amount=Money(Decimal("20"), "USD"),
            item_type=LineItemType.CREDIT,
        )
        adjusted = apply_adjustment(inv, credit)
        # The credit line reduces the subtotal
        assert len(adjusted.line_items) == len(inv.line_items) + 1


class TestVoidInvoice:
    """void_invoice() tests."""

    def test_void_invoice(
        self, sub_single_seat: Subscription, billing_period: BillingPeriod, tax_rates: dict
    ) -> None:
        inv = generate_invoice(sub_single_seat, billing_period, tax_rates)
        assert inv is not None
        voided = void_invoice(inv)
        assert voided.status == InvoiceStatus.VOIDED

    def test_void_paid_invoice_raises(self) -> None:
        inv = Invoice(
            invoice_id="inv-paid",
            customer_id="cust-001",
            issue_date=date(2025, 3, 1),
            due_date=date(2025, 3, 31),
            line_items=[LineItem(description="test", amount=Money(Decimal("10"), "USD"))],
            status=InvoiceStatus.PAID,
        )
        with pytest.raises(InvoiceError, match="Cannot void a PAID invoice"):
            void_invoice(inv)
