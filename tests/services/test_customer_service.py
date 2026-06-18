"""Tests for CustomerService — onboarding, plan changes, seat management, credit checks."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from dinarledger.core.enums import InvoiceStatus, SubscriptionStatus
from dinarledger.core.errors import (
    CreditLimitExceededError,
    DinarLedgerError,
    InvalidParameterError,
)
from dinarledger.core.money import Money
from dinarledger.core.types import (
    BillingPeriod,
    Customer,
    Invoice,
    LineItem,
    Plan,
    Subscription,
)
from dinarledger.services.customer_service import CustomerService
from dinarledger.storage.memory import MemoryRepository


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def customer_repo() -> MemoryRepository[Customer]:
    return MemoryRepository(Customer)


@pytest.fixture
def sub_repo() -> MemoryRepository[Subscription]:
    return MemoryRepository(Subscription)


@pytest.fixture
def invoice_repo() -> MemoryRepository[Invoice]:
    return MemoryRepository(Invoice)


@pytest.fixture
def svc(
    customer_repo: MemoryRepository[Customer],
    sub_repo: MemoryRepository[Subscription],
    invoice_repo: MemoryRepository[Invoice],
) -> CustomerService:
    return CustomerService(customer_repo, sub_repo, invoice_repo)


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
def annual_plan() -> Plan:
    return Plan(
        plan_id="plan-a",
        name="Pro Annual",
        base_price=Money(Decimal("999"), "USD"),
        billing_cycle="annual",
        trial_days=0,
    )


# ── Onboarding ──────────────────────────────────────────────────────────────

class TestOnboardCustomer:
    def test_basic_onboard(self, svc: CustomerService) -> None:
        customer = svc.onboard_customer("Acme Corp", "USD")
        assert customer.name == "Acme Corp"
        assert customer.currency == "USD"
        assert customer.credit_limit is None

    def test_onboard_with_credit_limit(self, svc: CustomerService) -> None:
        customer = svc.onboard_customer("Big Corp", "KWD", credit_limit=Decimal("5000"))
        assert customer.credit_limit == Money(Decimal("5000"), "KWD")

    def test_onboard_empty_name_raises(self, svc: CustomerService) -> None:
        with pytest.raises(InvalidParameterError, match="name"):
            svc.onboard_customer("   ", "USD")

    def test_onboard_with_custom_id(self, svc: CustomerService) -> None:
        customer = svc.onboard_customer("Test", "USD", customer_id="c-42")
        assert customer.customer_id == "c-42"

    def test_onboard_tax_exempt(self, svc: CustomerService) -> None:
        customer = svc.onboard_customer(
            "NonProfit", "USD", tax_exempt=True, tax_jurisdiction="KW"
        )
        assert customer.tax_exempt is True
        assert customer.tax_jurisdiction == "KW"


# ── Plan changes ────────────────────────────────────────────────────────────

class TestChangePlan:
    def test_change_plan_success(
        self,
        svc: CustomerService,
        customer_repo: MemoryRepository[Customer],
        sub_repo: MemoryRepository[Subscription],
        monthly_plan: Plan,
        annual_plan: Plan,
    ) -> None:
        customer = svc.onboard_customer("Acme", "USD", customer_id="c1")
        sub = Subscription(
            sub_id="s1",
            customer_id="c1",
            plan=monthly_plan,
            status=SubscriptionStatus.ACTIVE,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            seat_count=1,
        )
        sub_repo.add(sub)

        updated, net = svc.change_plan("c1", annual_plan, change_date=date(2025, 3, 1))
        assert updated.plan.plan_id == "plan-a"
        assert isinstance(net, Money)

    def test_change_plan_no_active_sub_raises(self, svc: CustomerService) -> None:
        with pytest.raises(DinarLedgerError, match="No active subscription"):
            svc.change_plan("nonexistent", monthly_plan)


# ── Seat management ─────────────────────────────────────────────────────────

class TestManageSeats:
    def test_add_seats(
        self,
        svc: CustomerService,
        sub_repo: MemoryRepository[Subscription],
        monthly_plan: Plan,
    ) -> None:
        svc.onboard_customer("Acme", "USD", customer_id="c1")
        sub = Subscription(
            sub_id="s1",
            customer_id="c1",
            plan=monthly_plan,
            status=SubscriptionStatus.ACTIVE,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 31),
            seat_count=1,
        )
        sub_repo.add(sub)

        updated, charge = svc.manage_seats("c1", 3, change_date=date(2025, 1, 1))
        assert updated.seat_count == 4
        assert charge.amount > Decimal("0")

    def test_remove_seats(
        self,
        svc: CustomerService,
        sub_repo: MemoryRepository[Subscription],
        monthly_plan: Plan,
    ) -> None:
        svc.onboard_customer("Acme", "USD", customer_id="c1")
        sub = Subscription(
            sub_id="s1",
            customer_id="c1",
            plan=monthly_plan,
            status=SubscriptionStatus.ACTIVE,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 31),
            seat_count=5,
        )
        sub_repo.add(sub)

        updated, credit = svc.manage_seats("c1", -2, change_date=date(2025, 1, 1))
        assert updated.seat_count == 3
        # credit should be negative (money back to customer)
        assert credit.amount < Decimal("0")

    def test_zero_delta_raises(self, svc: CustomerService) -> None:
        with pytest.raises(ValueError, match="non-zero"):
            svc.manage_seats("c1", 0)


# ── Credit checks ──────────────────────────────────────────────────────────

class TestCheckCredit:
    def test_within_limit(
        self,
        svc: CustomerService,
        customer_repo: MemoryRepository[Customer],
    ) -> None:
        customer = svc.onboard_customer("Acme", "USD", credit_limit=Decimal("1000"), customer_id="c1")
        assert svc.check_credit("c1", Money(Decimal("500"), "USD")) is True

    def test_exceeds_limit(
        self,
        svc: CustomerService,
        customer_repo: MemoryRepository[Customer],
        invoice_repo: MemoryRepository[Invoice],
    ) -> None:
        svc.onboard_customer("Acme", "USD", credit_limit=Decimal("500"), customer_id="c1")
        # Add an existing open invoice consuming $400 of the limit
        invoice_repo.add(Invoice(
            invoice_id="inv-1",
            customer_id="c1",
            issue_date=date(2025, 1, 1),
            due_date=date(2025, 1, 31),
            line_items=[LineItem(description="Charge", amount=Money(Decimal("400"), "USD"))],
            status=InvoiceStatus.OPEN,
        ))
        with pytest.raises(CreditLimitExceededError):
            svc.check_credit("c1", Money(Decimal("200"), "USD"))

    def test_unlimited_credit(
        self,
        svc: CustomerService,
    ) -> None:
        svc.onboard_customer("Unlimited", "USD", customer_id="c2")
        assert svc.check_credit("c2", Money(Decimal("999999"), "USD")) is True

    def test_unknown_customer_raises(self, svc: CustomerService) -> None:
        with pytest.raises(DinarLedgerError, match="not found"):
            svc.check_credit("ghost", Money(Decimal("1"), "USD"))


# ── Customer summary ────────────────────────────────────────────────────────

class TestGetCustomerSummary:
    def test_summary_returns_all_data(
        self,
        svc: CustomerService,
        sub_repo: MemoryRepository[Subscription],
        invoice_repo: MemoryRepository[Invoice],
        monthly_plan: Plan,
    ) -> None:
        svc.onboard_customer("Acme", "USD", customer_id="c1")
        sub_repo.add(Subscription(
            sub_id="s1",
            customer_id="c1",
            plan=monthly_plan,
            status=SubscriptionStatus.ACTIVE,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 31),
        ))
        invoice_repo.add(Invoice(
            invoice_id="inv-1",
            customer_id="c1",
            issue_date=date(2025, 1, 1),
            due_date=date(2025, 1, 31),
            line_items=[LineItem(description="X", amount=Money(Decimal("99"), "USD"))],
            status=InvoiceStatus.OPEN,
        ))

        summary = svc.get_customer_summary("c1")
        assert summary["customer"].customer_id == "c1"
        assert len(summary["subscriptions"]) == 1
        assert len(summary["invoices"]) == 1

    def test_summary_unknown_customer_raises(self, svc: CustomerService) -> None:
        with pytest.raises(DinarLedgerError, match="not found"):
            svc.get_customer_summary("ghost")
