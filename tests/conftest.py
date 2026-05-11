"""Shared pytest fixtures for DinarLedger test suite."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from dinarledger.core.enums import InvoiceStatus, SubscriptionStatus
from dinarledger.core.money import Money, zero as _zero
from dinarledger.core.types import (
    BillingPeriod,
    Customer,
    Invoice,
    LineItem,
    Payment,
    PaymentStatus,
    Plan,
    Subscription,
    TaxRate,
)


# ── Date fixtures ────────────────────────────────────────────────────────

@pytest.fixture
def today() -> date:
    """A deterministic "today" for tests."""
    return date(2025, 3, 15)


@pytest.fixture
def first_of_month() -> date:
    """First day of a month for tests."""
    return date(2025, 3, 1)


# ── Customer ─────────────────────────────────────────────────────────────

@pytest.fixture
def sample_customer() -> Customer:
    """An Egyptian-customer with a 50 000 EGP credit limit."""
    return Customer(
        customer_id="cust-001",
        name="Al-Rayan Industries",
        currency="EGP",
        credit_limit=Money(Decimal("50000"), "EGP"),
    )


# ── Plans ────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_plan_monthly() -> Plan:
    """$99/month plan with a 14-day trial and no setup fee."""
    return Plan(
        plan_id="plan-monthly",
        name="Professional Monthly",
        base_price=Money(Decimal("99"), "USD"),
        billing_cycle="monthly",
        setup_fee=None,
        trial_days=14,
    )


@pytest.fixture
def sample_plan_annual() -> Plan:
    """$999/year plan with a $99 setup fee."""
    return Plan(
        plan_id="plan-annual",
        name="Professional Annual",
        base_price=Money(Decimal("999"), "USD"),
        billing_cycle="annual",
        setup_fee=Money(Decimal("99"), "USD"),
        trial_days=0,
    )


# ── Subscription ─────────────────────────────────────────────────────────

@pytest.fixture
def sample_subscription(sample_plan_monthly: Plan) -> Subscription:
    """An ACTIVE subscription on the monthly plan."""
    return Subscription(
        sub_id="sub-001",
        customer_id="cust-001",
        plan=sample_plan_monthly,
        status=SubscriptionStatus.ACTIVE,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 31),
        seat_count=1,
    )


# ── Invoice ──────────────────────────────────────────────────────────────

@pytest.fixture
def sample_invoice() -> Invoice:
    """An OPEN invoice with 3 line items totalling $347."""
    return Invoice(
        invoice_id="inv-001",
        customer_id="cust-001",
        issue_date=date(2025, 3, 1),
        due_date=date(2025, 3, 31),
        line_items=[
            LineItem(
                description="Professional Monthly — recurring (1 seat(s))",
                amount=Money(Decimal("99"), "USD"),
            ),
            LineItem(
                description="Add-on: Extra storage",
                amount=Money(Decimal("49"), "USD"),
            ),
            LineItem(
                description="Add-on: Priority support",
                amount=Money(Decimal("199"), "USD"),
            ),
        ],
        status=InvoiceStatus.OPEN,
    )


# ── Payment ──────────────────────────────────────────────────────────────

@pytest.fixture
def sample_payment() -> Payment:
    """A completed payment record."""
    return Payment(
        payment_id="pay-001",
        invoice_id="inv-001",
        amount=Money(Decimal("347"), "USD"),
        status=PaymentStatus.COMPLETED,
        paid_date=date(2025, 3, 5),
        reference="TXN-12345",
    )


# ── Tax rates ────────────────────────────────────────────────────────────

@pytest.fixture
def sample_tax_rates() -> dict[str, TaxRate]:
    """Standard Egyptian VAT rates used in tests."""
    return {
        "standard": TaxRate(
            code="VAT-14",
            rate=Decimal("0.14"),
            description="Standard VAT 14%",
        ),
        "reduced": TaxRate(
            code="VAT-5",
            rate=Decimal("0.05"),
            description="Reduced rate 5%",
        ),
        "exempt": TaxRate(
            code="VAT-0",
            rate=Decimal("0"),
            description="Exempt",
            is_exempt=True,
        ),
    }
