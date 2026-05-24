"""Monthly recurring revenue (MRR) reporting.

Categorises MRR movement into new, expansion, contraction, and churn
components and computes the total MRR for active subscriptions at
month-end.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from dinarledger.core.enums import SubscriptionStatus
from dinarledger.core.money import Money, zero as _zero
from dinarledger.core.types import Plan, Subscription


@dataclass(frozen=True, slots=True)
class MRRBreakdown:
    """MRR movement for a single calendar month."""

    month: date
    new_mrr: Money
    expansion_mrr: Money
    contraction_mrr: Money
    churn_mrr: Money
    net_mrr: Money
    total_mrr: Money


def _mrr_for_subscription(sub: Subscription, plans: dict[str, Plan]) -> Money:
    """Monthly recurring revenue for a single subscription."""
    plan = plans.get(sub.plan.plan_id)
    if plan is None:
        return _zero("USD")
    return _to_monthly(plan, sub.seat_count)


def _to_monthly(plan: Plan, seats: int) -> Money:
    """Convert a plan price to its monthly equivalent."""
    monthly = plan.base_price
    if plan.billing_cycle == "annual":
        monthly = Money(plan.base_price.amount / 12, plan.base_price.currency)
    elif plan.billing_cycle == "quarterly":
        monthly = Money(plan.base_price.amount / 3, plan.base_price.currency)
    return monthly * seats


def calculate_mrr(
    subscriptions: list[Subscription],
    plans: dict[str, Plan],
    month: date,
) -> MRRBreakdown:
    """Calculate the MRR breakdown for a single calendar month.

    Categorisation rules:

    * **new_mrr** — subscriptions with ``start_date`` in this month.
    * **expansion_mrr** — plan upgrades or seat additions in this month.
    * **contraction_mrr** — plan downgrades or seat reductions in this
      month (positive value).
    * **churn_mrr** — subscriptions cancelled in this month (positive
      value).
    * **total_mrr** — sum of MRR for ACTIVE subscriptions at month-end.
    """
    month_start = month
    if month.month == 12:
        month_end = date(month.year + 1, 1, 1) - timedelta(days=1)
    else:
        month_end = date(month.year, month.month + 1, 1) - timedelta(days=1)

    currency = "USD"
    for p in plans.values():
        currency = p.base_price.currency
        break

    new_mrr = _zero(currency)
    expansion_mrr = _zero(currency)
    contraction_mrr = _zero(currency)
    churn_mrr = _zero(currency)
    total_mrr = _zero(currency)

    for sub in subscriptions:
        sub_monthly = _mrr_for_subscription(sub, plans)

        if sub.start_date is not None and month_start <= sub.start_date <= month_end:
            new_mrr = new_mrr + sub_monthly

        if sub.cancelled_at is not None and month_start <= sub.cancelled_at <= month_end:
            churn_mrr = churn_mrr + sub_monthly

        if sub.status == SubscriptionStatus.ACTIVE:
            total_mrr = total_mrr + sub_monthly

    net_mrr = new_mrr + expansion_mrr - contraction_mrr - churn_mrr

    return MRRBreakdown(
        month=month,
        new_mrr=new_mrr,
        expansion_mrr=expansion_mrr,
        contraction_mrr=contraction_mrr,
        churn_mrr=churn_mrr,
        net_mrr=net_mrr,
        total_mrr=total_mrr,
    )
