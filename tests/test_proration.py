"""Tests for dinarledger.plans.proration — mid-cycle plan changes."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from dinarledger.core.money import Money
from dinarledger.core.types import BillingPeriod, Plan
from dinarledger.plans.proration import (
    calculate_upgrade_charge,
    calculate_upgrade_credit,
    net_upgrade_amount,
    prorate,
)


@pytest.fixture
def monthly_plan() -> Plan:
    return Plan(
        plan_id="plan-basic",
        name="Basic Monthly",
        base_price=Money(Decimal("99"), "USD"),
        billing_cycle="monthly",
    )


@pytest.fixture
def premium_plan() -> Plan:
    return Plan(
        plan_id="plan-premium",
        name="Premium Monthly",
        base_price=Money(Decimal("199"), "USD"),
        billing_cycle="monthly",
    )


@pytest.fixture
def period() -> BillingPeriod:
    """A 31-day January period."""
    return BillingPeriod(start_date=date(2025, 1, 1), end_date=date(2025, 1, 31))


class TestProrate:
    """prorate() tests."""

    def test_prorate_full_period(self, monthly_plan: Plan, period: BillingPeriod) -> None:
        """Prorating the full period returns the full price."""
        result = prorate(
            monthly_plan, period, period.start_date, period.end_date
        )
        assert result == monthly_plan.base_price

    def test_prorate_mid_month(self, monthly_plan: Plan, period: BillingPeriod) -> None:
        """Prorating from mid-month returns roughly half."""
        change = date(2025, 1, 16)
        result = prorate(monthly_plan, period, change, period.end_date)
        # 16 days remaining out of 31 (inclusive: Jan 16–31 = 16 days)
        fraction = Decimal(16) / Decimal(31)
        expected = monthly_plan.base_price * fraction
        assert abs(result.amount - expected.amount) < Decimal("0.01")


class TestUpgradeCredit:
    """calculate_upgrade_credit tests."""

    def test_upgrade_credit(self, monthly_plan: Plan, premium_plan: Plan, period: BillingPeriod) -> None:
        """Credit for unused portion of the old plan after the change date."""
        change = date(2025, 1, 16)
        credit = calculate_upgrade_credit(monthly_plan, premium_plan, period, change)
        assert credit.amount > Decimal("0")
        assert credit.amount < monthly_plan.base_price.amount


class TestUpgradeCharge:
    """calculate_upgrade_charge tests."""

    def test_upgrade_charge(self, premium_plan: Plan, period: BillingPeriod) -> None:
        """Charge for the new plan from change date to period end."""
        change = date(2025, 1, 16)
        charge = calculate_upgrade_charge(premium_plan, period, change)
        assert charge.amount > Decimal("0")
        assert charge.amount < premium_plan.base_price.amount


class TestNetUpgrade:
    """net_upgrade_amount tests."""

    def test_net_upgrade_positive(
        self, monthly_plan: Plan, premium_plan: Plan, period: BillingPeriod
    ) -> None:
        """Upgrading from basic ($99) to premium ($199) mid-month → net positive."""
        change = date(2025, 1, 16)
        net = net_upgrade_amount(monthly_plan, premium_plan, period, change)
        # Charge should exceed credit because premium is more expensive
        assert net.amount > Decimal("0")

    def test_net_upgrade_negative(
        self, premium_plan: Plan, monthly_plan: Plan, period: BillingPeriod
    ) -> None:
        """Downgrading from premium ($199) to basic ($99) mid-month → net negative (customer gets credit)."""
        change = date(2025, 1, 16)
        net = net_upgrade_amount(premium_plan, monthly_plan, period, change)
        # Credit should exceed charge because basic is cheaper
        assert net.amount < Decimal("0")
