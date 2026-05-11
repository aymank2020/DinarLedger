"""Tests for dinarledger.subscriptions.lifecycle — subscription state machine."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from dinarledger.core.enums import SubscriptionStatus
from dinarledger.core.errors import SubscriptionStateError
from dinarledger.core.money import Money
from dinarledger.core.types import Plan
from dinarledger.subscriptions.lifecycle import (
    activate,
    cancel_subscription,
    change_plan,
    reactivate,
    subscribe,
)


@pytest.fixture
def plan_with_trial() -> Plan:
    return Plan(
        plan_id="plan-trial",
        name="Pro Monthly",
        base_price=Money(Decimal("99"), "USD"),
        billing_cycle="monthly",
        trial_days=14,
    )


@pytest.fixture
def plan_no_trial() -> Plan:
    return Plan(
        plan_id="plan-direct",
        name="Business Monthly",
        base_price=Money(Decimal("149"), "USD"),
        billing_cycle="monthly",
        trial_days=0,
    )


@pytest.fixture
def start_date() -> date:
    return date(2025, 3, 1)


class TestSubscribe:
    """subscribe() tests."""

    def test_subscribe_with_trial(self, plan_with_trial: Plan, start_date: date) -> None:
        sub = subscribe("cust-001", plan_with_trial, start_date)
        assert sub.status == SubscriptionStatus.TRIAL
        assert sub.start_date == start_date
        assert sub.plan.plan_id == "plan-trial"
        assert sub.seat_count == 1

    def test_subscribe_no_trial(self, plan_no_trial: Plan, start_date: date) -> None:
        sub = subscribe("cust-001", plan_no_trial, start_date)
        assert sub.status == SubscriptionStatus.ACTIVE
        assert sub.plan.plan_id == "plan-direct"


class TestActivate:
    """activate() tests."""

    def test_activate(self, plan_with_trial: Plan, start_date: date) -> None:
        sub = subscribe("cust-001", plan_with_trial, start_date)
        assert sub.status == SubscriptionStatus.TRIAL
        activated = activate(sub)
        assert activated.status == SubscriptionStatus.ACTIVE

    def test_activate_non_trial_raises(self, plan_no_trial: Plan, start_date: date) -> None:
        sub = subscribe("cust-001", plan_no_trial, start_date)
        # Already ACTIVE, not TRIAL
        with pytest.raises(SubscriptionStateError):
            activate(sub)


class TestChangePlan:
    """change_plan() tests."""

    def test_change_plan(
        self, plan_no_trial: Plan, plan_with_trial: Plan, start_date: date
    ) -> None:
        sub = subscribe("cust-001", plan_no_trial, start_date)
        # Subscription needs an end_date for proration
        assert sub.end_date is not None
        updated, net = change_plan(sub, plan_with_trial, start_date + timedelta(days=10))
        assert updated.plan.plan_id == "plan-trial"
        # Net upgrade amount should be a Money object
        assert isinstance(net.amount, Decimal)


class TestCancel:
    """cancel_subscription() tests."""

    def test_cancel_immediate(self, plan_no_trial: Plan, start_date: date) -> None:
        sub = subscribe("cust-001", plan_no_trial, start_date)
        cancel_date = start_date + timedelta(days=5)
        cancelled = cancel_subscription(sub, cancel_date, immediate=True)
        assert cancelled.status == SubscriptionStatus.CANCELLED
        assert cancelled.cancelled_at == cancel_date

    def test_cancel_end_of_period(self, plan_no_trial: Plan, start_date: date) -> None:
        sub = subscribe("cust-001", plan_no_trial, start_date)
        cancel_date = start_date + timedelta(days=5)
        cancelled = cancel_subscription(sub, cancel_date, immediate=False)
        # Status remains ACTIVE (deferred cancellation)
        assert cancelled.status == SubscriptionStatus.ACTIVE
        assert cancelled.cancelled_at == cancel_date


class TestReactivate:
    """reactivate() tests."""

    def test_reactivate_within_30_days(self, plan_no_trial: Plan, start_date: date) -> None:
        sub = subscribe("cust-001", plan_no_trial, start_date)
        cancel_date = start_date + timedelta(days=5)
        cancelled = cancel_subscription(sub, cancel_date, immediate=True)

        reactivate_date = cancel_date + timedelta(days=15)
        reactivated = reactivate(cancelled, reactivate_date)
        assert reactivated.status == SubscriptionStatus.ACTIVE
        assert reactivated.cancelled_at is None

    def test_reactivate_beyond_30_days_raises(self, plan_no_trial: Plan, start_date: date) -> None:
        sub = subscribe("cust-001", plan_no_trial, start_date)
        cancel_date = start_date + timedelta(days=5)
        cancelled = cancel_subscription(sub, cancel_date, immediate=True)

        reactivate_date = cancel_date + timedelta(days=31)
        with pytest.raises(SubscriptionStateError):
            reactivate(cancelled, reactivate_date)
