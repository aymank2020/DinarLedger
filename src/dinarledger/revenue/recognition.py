"""IFRS 15 revenue recognition.

Implements step 4 (allocate the transaction price) and step 5 (recognise
revenue when/as performance obligations are satisfied) of the IFRS 15 /
ASC 606 model.

A :class:`PerformanceObligation` is either *satisfied over time* (revenue
recognised ratably between ``start_date`` and ``end_date``) or *satisfied
at a point in time* (recognised in full once ``end_date`` falls within the
billing period). Allocation uses the ratio of each obligation's
standalone selling price to the total of all standalone prices.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Sequence

from dinarledger.core.money import Money, zero
from dinarledger.core.types import BillingPeriod


@dataclass(frozen=True)
class PerformanceObligation:
    """A distinct performance obligation within a contract.

    Attributes:
        obligation_id: Unique identifier for this obligation.
        description: Human-readable description of the good/service.
        standalone_price: Standalone selling price used for allocation.
        satisfied_over_time: ``True`` for ratable recognition, ``False``
            for point-in-time recognition.
        start_date: Date performance begins.
        end_date: Date performance is completed; ``None`` for perpetual
            obligations.
    """

    obligation_id: str
    description: str
    standalone_price: Money
    satisfied_over_time: bool
    start_date: date
    end_date: date | None = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _total_standalone_price(obligations: Sequence[PerformanceObligation]) -> Money:
    if not obligations:
        return zero("USD")
    currency = obligations[0].standalone_price.currency
    total = zero(currency)
    for obl in obligations:
        if obl.standalone_price.currency != currency:
            raise ValueError(
                f"Currency mismatch: expected {currency}, "
                f"got {obl.standalone_price.currency} on {obl.obligation_id}"
            )
        total = total + obl.standalone_price
    return total


def _allocated_price(
    obligation: PerformanceObligation,
    total_standalone: Money,
    total_transaction_price: Money,
) -> Money:
    """Allocate the transaction price to a single obligation by SSP ratio."""
    if total_standalone.is_zero():
        return zero(total_transaction_price.currency)

    ratio = obligation.standalone_price.amount / total_standalone.amount
    allocated_amount = total_transaction_price.amount * ratio
    return Money(
        amount=allocated_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        currency=total_transaction_price.currency,
    )


def _months_between(start: date, end: date) -> int:
    return (end.year - start.year) * 12 + (end.month - start.month) + 1


def _days_in_month(d: date) -> int:
    return calendar.monthrange(d.year, d.month)[1]


def _days_active_in_month(obligation: PerformanceObligation, ref_month: date) -> int:
    year, month = ref_month.year, ref_month.month
    month_start = date(year, month, 1)
    month_end = date(year, month, _days_in_month(ref_month))

    ob_start = max(obligation.start_date, month_start)
    ob_end_val = obligation.end_date or date(9999, 12, 31)
    ob_end = min(ob_end_val, month_end)

    if ob_start > ob_end:
        return 0
    return (ob_end - ob_start).days + 1


def _next_month(d: date) -> date:
    if d.month == 12:
        return date(d.year + 1, 1, 1)
    return date(d.year, d.month + 1, 1)


# ---------------------------------------------------------------------------
# recognize_revenue
# ---------------------------------------------------------------------------

def recognize_revenue(
    obligations: list[PerformanceObligation],
    total_transaction_price: Money,
    period: BillingPeriod,
) -> list[tuple[str, Money]]:
    """Recognise revenue for each performance obligation within *period*.

    Over-time obligations recognise

        allocated_price / total_months × (days_active / days_in_month)

    for stub months and ``allocated_price / total_months`` for full months.
    Point-in-time obligations recognise the full allocated amount when the
    obligation's ``end_date`` falls inside *period*.

    Returns a ``(obligation_id, recognised_amount)`` tuple for every
    obligation.
    """
    if not obligations:
        return []

    total_standalone = _total_standalone_price(obligations)

    if total_standalone.is_zero():
        return [
            (obl.obligation_id, zero(total_transaction_price.currency))
            for obl in obligations
        ]

    results: list[tuple[str, Money]] = []

    for obl in obligations:
        allocated = _allocated_price(obl, total_standalone, total_transaction_price)

        if obl.satisfied_over_time:
            if obl.end_date is None:
                results.append((obl.obligation_id, zero(allocated.currency)))
                continue

            ob_end = obl.end_date
            if obl.start_date > period.end_date or ob_end < period.start_date:
                results.append((obl.obligation_id, zero(allocated.currency)))
                continue

            total_months = _months_between(obl.start_date, ob_end)
            if total_months <= 0:
                results.append((obl.obligation_id, zero(allocated.currency)))
                continue

            monthly_amount = Money(
                amount=(allocated.amount / total_months).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                ),
                currency=allocated.currency,
            )

            recognized = zero(allocated.currency)
            cur = date(period.start_date.year, period.start_date.month, 1)
            while cur <= period.end_date:
                days_active = _days_active_in_month(obl, cur)
                days_total = _days_in_month(cur)

                if days_active <= 0:
                    cur = _next_month(cur)
                    continue

                if days_active == days_total:
                    recognized = recognized + monthly_amount
                else:
                    daily_rate = monthly_amount.amount / days_total
                    stub_amount = daily_rate * days_active
                    recognized = recognized + Money(
                        amount=stub_amount.quantize(
                            Decimal("0.01"), rounding=ROUND_HALF_UP
                        ),
                        currency=allocated.currency,
                    )

                cur = _next_month(cur)

            results.append((obl.obligation_id, recognized))

        else:
            # Point-in-time: recognise on satisfaction date
            if (
                obl.end_date is not None
                and period.start_date <= obl.end_date <= period.end_date
            ):
                results.append((obl.obligation_id, allocated))
            else:
                results.append((obl.obligation_id, zero(allocated.currency)))

    return results


# ---------------------------------------------------------------------------
# calculate_deferred
# ---------------------------------------------------------------------------

def calculate_deferred(
    obligations: list[PerformanceObligation],
    total_transaction_price: Money,
    as_of: date,
) -> Money:
    """Deferred revenue across all obligations as of *as_of*.

    Computed as ``sum(allocated_price - cumulative_recognised)`` per
    obligation. Negative balances (rounding artefacts) are clamped to zero.
    """
    if not obligations:
        return zero(total_transaction_price.currency)

    total_standalone = _total_standalone_price(obligations)

    if total_standalone.is_zero():
        return zero(total_transaction_price.currency)

    deferred = zero(total_transaction_price.currency)

    for obl in obligations:
        allocated = _allocated_price(obl, total_standalone, total_transaction_price)

        if obl.satisfied_over_time:
            if obl.end_date is None:
                deferred = deferred + allocated
                continue

            if as_of < obl.start_date:
                deferred = deferred + allocated
                continue

            if as_of >= obl.end_date:
                continue

            total_months = _months_between(obl.start_date, obl.end_date)
            if total_months <= 0:
                continue

            monthly_amount = Money(
                amount=(allocated.amount / total_months).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                ),
                currency=allocated.currency,
            )

            cumulative = zero(allocated.currency)
            cur = date(obl.start_date.year, obl.start_date.month, 1)
            end_month = date(as_of.year, as_of.month, 1)
            while cur <= end_month:
                days_active = _days_active_in_month(obl, cur)
                days_total = _days_in_month(cur)

                if days_active <= 0:
                    cur = _next_month(cur)
                    continue

                if days_active == days_total:
                    cumulative = cumulative + monthly_amount
                else:
                    daily_rate = monthly_amount.amount / days_total
                    stub_amount = daily_rate * days_active
                    cumulative = cumulative + Money(
                        amount=stub_amount.quantize(
                            Decimal("0.01"), rounding=ROUND_HALF_UP
                        ),
                        currency=allocated.currency,
                    )

                cur = _next_month(cur)

            obligation_deferred = allocated - cumulative
            if obligation_deferred.amount >= Decimal("0"):
                deferred = deferred + obligation_deferred

        else:
            if obl.end_date is not None and as_of >= obl.end_date:
                continue
            deferred = deferred + allocated

    return deferred
