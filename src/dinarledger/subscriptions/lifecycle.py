"""
Subscription lifecycle management.

State transitions:

    TRIAL --activate()--> ACTIVE --cancel(immediate=True)--> CANCELLED
                          ACTIVE --cancel(immediate=False)--> ACTIVE (cancelled_at set)

A deferred cancellation (``immediate=False``) sets ``cancelled_at`` while
keeping ``status=ACTIVE``; downstream modules use ``cancelled_at`` to detect
the pending termination.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from typing import Optional

from dinarledger.core.errors import SubscriptionStateError
from dinarledger.core.money import Money
from dinarledger.core.types import BillingPeriod, Plan, Subscription, SubscriptionStatus
from dinarledger.plans.proration import net_upgrade_amount as _net_upgrade_amount


# Maximum days after cancellation that a customer may reactivate.
REACTIVATION_WINDOW_DAYS = 30


# ── Public API ──────────────────────────────────────────────────────────────

def subscribe(
    customer_id: str,
    plan: Plan,
    start_date: date,
    seat_count: int = 1,
) -> Subscription:
    """Create a new subscription for a customer.

    If ``plan.trial_days > 0`` the subscription starts in ``TRIAL`` state;
    otherwise it starts as ``ACTIVE``. The ``end_date`` is the last day of
    the initial billing period derived from ``plan.billing_cycle``.
    """
    if seat_count < 1:
        raise ValueError(f"seat_count must be >= 1, got {seat_count}")

    period_end = _period_end(start_date, plan.billing_cycle)

    status = (
        SubscriptionStatus.TRIAL
        if plan.trial_days > 0
        else SubscriptionStatus.ACTIVE
    )

    return Subscription(
        sub_id=_generate_sub_id(),
        customer_id=customer_id,
        plan=plan,
        status=status,
        start_date=start_date,
        end_date=period_end,
        seat_count=seat_count,
        cancelled_at=None,
    )


def activate(subscription: Subscription) -> Subscription:
    """Transition a subscription from TRIAL to ACTIVE.

    Raises :class:`SubscriptionStateError` if the subscription is not in
    ``TRIAL`` state.
    """
    if subscription.status != SubscriptionStatus.TRIAL:
        raise SubscriptionStateError(
            sub_id=subscription.sub_id,
            current_state=subscription.status.value,
            attempted_action="activate",
        )

    return replace(subscription, status=SubscriptionStatus.ACTIVE)


def change_plan(
    subscription: Subscription,
    new_plan: Plan,
    change_date: date,
) -> tuple[Subscription, Money]:
    """Change the plan on an active subscription.

    Returns the updated subscription and the net upgrade amount (positive
    if the customer owes money, negative for a credit).
    """
    if subscription.status != SubscriptionStatus.ACTIVE:
        raise SubscriptionStateError(
            sub_id=subscription.sub_id,
            current_state=subscription.status.value,
            attempted_action="change_plan",
        )

    if subscription.end_date is None:
        raise ValueError(
            f"Cannot change plan on subscription {subscription.sub_id} "
            f"with no end_date"
        )

    period = BillingPeriod(
        start_date=subscription.start_date,
        end_date=subscription.end_date,
    )

    net = _net_upgrade_amount(subscription.plan, new_plan, period, change_date)
    updated = replace(subscription, plan=new_plan)
    return updated, net


def cancel_subscription(
    subscription: Subscription,
    cancel_date: date,
    immediate: bool = False,
) -> Subscription:
    """Cancel a subscription.

    With ``immediate=True`` the status moves to ``CANCELLED`` right away.
    With ``immediate=False`` the status remains ``ACTIVE`` and only
    ``cancelled_at`` is recorded; the cancellation takes effect at the
    end of the current billing period.
    """
    if subscription.status == SubscriptionStatus.CANCELLED:
        raise SubscriptionStateError(
            sub_id=subscription.sub_id,
            current_state=subscription.status.value,
            attempted_action="cancel",
        )
    if subscription.status == SubscriptionStatus.EXPIRED:
        raise SubscriptionStateError(
            sub_id=subscription.sub_id,
            current_state=subscription.status.value,
            attempted_action="cancel",
        )

    if immediate:
        return replace(
            subscription,
            status=SubscriptionStatus.CANCELLED,
            cancelled_at=cancel_date,
        )

    return replace(subscription, cancelled_at=cancel_date)


def reactivate(
    subscription: Subscription,
    reactivate_date: date,
) -> Subscription:
    """Reactivate a previously cancelled subscription.

    Reactivation is only allowed within :data:`REACTIVATION_WINDOW_DAYS`
    of the cancellation date. Returns a subscription with status set to
    ``ACTIVE`` and ``cancelled_at`` cleared.
    """
    if subscription.cancelled_at is not None:
        days_since_cancel = (reactivate_date - subscription.cancelled_at).days
        if days_since_cancel > REACTIVATION_WINDOW_DAYS:
            raise SubscriptionStateError(
                sub_id=subscription.sub_id,
                current_state=subscription.status.value,
                attempted_action="reactivate",
            )

    return replace(
        subscription,
        status=SubscriptionStatus.ACTIVE,
        cancelled_at=None,
    )


# ── Internal helpers ────────────────────────────────────────────────────────

def _period_end(start: date, billing_cycle: str) -> date:
    """Compute the end date of the initial billing period."""
    if billing_cycle == "monthly":
        return _month_end(start)
    if billing_cycle == "quarterly":
        return _quarter_end(start)
    if billing_cycle == "annual":
        return _annual_end(start)
    return _month_end(start)


def _month_end(start: date) -> date:
    if start.month == 12:
        next_month_start = date(start.year + 1, 1, 1)
    else:
        next_month_start = date(start.year, start.month + 1, 1)
    return next_month_start - timedelta(days=1)


def _quarter_end(start: date) -> date:
    target_month = start.month + 3
    target_year = start.year + (target_month - 1) // 12
    target_month = ((target_month - 1) % 12) + 1

    if target_month == 12:
        next_start = date(target_year + 1, 1, start.day)
    else:
        try:
            next_start = date(target_year, target_month + 1, start.day)
        except ValueError:
            import calendar
            last_day = calendar.monthrange(target_year, target_month + 1)[1]
            next_start = date(target_year, target_month + 1, last_day)
    return next_start - timedelta(days=1)


def _annual_end(start: date) -> date:
    try:
        next_year_start = date(start.year + 1, start.month, start.day)
    except ValueError:
        next_year_start = date(start.year + 1, start.month, 28)
    return next_year_start - timedelta(days=1)


_sub_counter = 0


def _generate_sub_id() -> str:
    global _sub_counter
    _sub_counter += 1
    return f"sub-{_sub_counter}"
