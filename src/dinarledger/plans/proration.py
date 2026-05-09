"""
Proration logic for mid-cycle plan changes.

When a customer upgrades or downgrades partway through a billing period,
the unused portion of the old plan is credited and the remaining portion
of the new plan is charged. Both calculations use a daily rate derived
from the plan price and the period length.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from dinarledger.core.money import Money, zero
from dinarledger.core.period import proration_fraction
from dinarledger.core.types import BillingPeriod, Plan


def prorate(
    plan: Plan,
    period: BillingPeriod,
    active_start: date,
    active_end: date,
) -> Money:
    """Prorated charge for a partial billing period.

    Returns ``plan.base_price × proration_fraction(period, active_interval)``,
    or zero if the active interval falls outside the period.
    """
    fraction = proration_fraction(period, active_start, active_end)
    return plan.base_price * fraction


def calculate_upgrade_credit(
    old_plan: Plan,
    new_plan: Plan,
    period: BillingPeriod,
    change_date: date,
) -> Money:
    """Credit for the unused portion of the old plan from *change_date*
    through the end of *period*.

    Daily rate = ``old_plan.base_price.amount / period.days``.
    Returns zero if *change_date* falls after the period end.
    """
    if change_date > period.end_date:
        return zero(old_plan.base_price.currency)

    effective_start = max(change_date, period.start_date)
    unused_days = (period.end_date - effective_start).days + 1

    daily_rate = old_plan.base_price.amount / Decimal(period.days)
    credit_amount = (daily_rate * unused_days).quantize(Decimal("0.01"))
    return Money(amount=credit_amount, currency=old_plan.base_price.currency)


def calculate_upgrade_charge(
    new_plan: Plan,
    period: BillingPeriod,
    change_date: date,
) -> Money:
    """Charge for the new plan from *change_date* through the end of *period*.

    Daily rate = ``new_plan.base_price.amount / period.days``.
    Returns zero if *change_date* falls after the period end.
    """
    if change_date > period.end_date:
        return zero(new_plan.base_price.currency)

    effective_start = max(change_date, period.start_date)
    remaining_days = (period.end_date - effective_start).days + 1

    daily_rate = new_plan.base_price.amount / Decimal(period.days)
    charge_amount = (daily_rate * remaining_days).quantize(Decimal("0.01"))
    return Money(amount=charge_amount, currency=new_plan.base_price.currency)


def net_upgrade_amount(
    old_plan: Plan,
    new_plan: Plan,
    period: BillingPeriod,
    change_date: date,
) -> Money:
    """Net amount due for a mid-cycle plan change.

    Equals ``calculate_upgrade_charge - calculate_upgrade_credit``.
    Positive = customer owes; negative = customer is credited.
    """
    charge = calculate_upgrade_charge(new_plan, period, change_date)
    credit = calculate_upgrade_credit(old_plan, new_plan, period, change_date)
    return charge - credit
