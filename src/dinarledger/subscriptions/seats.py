"""
Per-seat pricing.

Plans are priced per seat: the ``base_price`` represents one seat, and
each additional seat is billed at the same rate. This module computes
seat costs and handles mid-cycle additions/removals with proration.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

from dinarledger.core.money import Money
from dinarledger.core.period import proration_fraction
from dinarledger.core.types import BillingPeriod, Plan, Subscription


def seat_cost(plan: Plan, seat_count: int) -> Money:
    """Total cost for *seat_count* seats on *plan*.

    Equals ``plan.base_price × seat_count``.
    """
    if seat_count < 1:
        raise ValueError(f"seat_count must be >= 1, got {seat_count}")

    return plan.base_price * seat_count


def add_seats(
    subscription: Subscription,
    additional: int,
    change_date: date,
    period: BillingPeriod,
) -> tuple[Subscription, Money]:
    """Add *additional* seats to *subscription*, returning the prorated charge.

    The charge covers the remaining portion of the current billing period.
    """
    if additional < 1:
        raise ValueError(f"additional seats must be >= 1, got {additional}")

    per_seat_rate = subscription.plan.base_price
    total_additional_cost = per_seat_rate * additional

    fraction = proration_fraction(period, change_date, period.end_date)
    prorated_charge = total_additional_cost * fraction

    updated = replace(subscription, seat_count=subscription.seat_count + additional)
    return updated, prorated_charge


def remove_seats(
    subscription: Subscription,
    removed: int,
    change_date: date,
    period: BillingPeriod,
) -> tuple[Subscription, Money]:
    """Remove *removed* seats from *subscription*, returning the prorated credit.

    At least one seat must remain; use ``cancel_subscription`` to terminate
    a subscription entirely.
    """
    if removed < 1:
        raise ValueError(f"removed seats must be >= 1, got {removed}")
    if removed >= subscription.seat_count:
        raise ValueError(
            f"Cannot remove {removed} seats from subscription with "
            f"{subscription.seat_count} seats; at least 1 seat must remain."
        )

    per_seat_rate = subscription.plan.base_price
    total_removed_value = per_seat_rate * removed

    fraction = proration_fraction(period, change_date, period.end_date)
    prorated_credit = total_removed_value * fraction

    updated = replace(subscription, seat_count=subscription.seat_count - removed)
    return updated, prorated_credit
