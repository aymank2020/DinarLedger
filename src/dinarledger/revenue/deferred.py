"""Deferred revenue schedule — monthly roll-forward.

Generates a month-by-month schedule (beginning balance, recognised,
additions, ending balance) for a set of performance obligations.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from dinarledger.core.money import Money, zero
from dinarledger.revenue.recognition import (
    PerformanceObligation,
    _allocated_price,
    _days_active_in_month,
    _days_in_month,
    _months_between,
    _next_month,
    _total_standalone_price,
)


@dataclass(frozen=True)
class DeferredEntry:
    """One row in a deferred revenue roll-forward schedule.

    Attributes:
        date: Last calendar day of the month the entry represents.
        beginning_balance: Deferred revenue at start of month.
        recognized: Revenue recognised during the month.
        additions: New deferred revenue from obligations starting this month.
        ending_balance: ``beginning_balance - recognized + additions``.
    """

    date: date
    beginning_balance: Money
    recognized: Money
    additions: Money
    ending_balance: Money


def stub_period_amortization(
    obligation: PerformanceObligation,
    total_transaction_price: Money,
    period_month: date,
) -> Money:
    """Amortisation amount for a stub (partial) month.

    For the first stub month the amount is prorated by ``days_active``.
    """
    total_standalone = _total_standalone_price([obligation])
    allocated = _allocated_price(obligation, total_standalone, total_transaction_price)

    if obligation.end_date is None:
        return zero(allocated.currency)

    total_months = _months_between(obligation.start_date, obligation.end_date)
    if total_months <= 0:
        return zero(allocated.currency)

    monthly_amount = Money(
        amount=(allocated.amount / total_months).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        ),
        currency=allocated.currency,
    )

    days_active = _days_active_in_month(obligation, period_month)
    days_total = _days_in_month(period_month)

    if days_active <= 0:
        return zero(allocated.currency)

    is_first_stub = (
        obligation.start_date.year == period_month.year
        and obligation.start_date.month == period_month.month
        and obligation.start_date.day > 1
    )
    is_last_stub = (
        obligation.end_date is not None
        and obligation.end_date.year == period_month.year
        and obligation.end_date.month == period_month.month
        and obligation.end_date.day < days_total
    )

    if is_first_stub:
        daily_rate = monthly_amount.amount / days_total
        stub_amount = daily_rate * days_active
        return Money(
            amount=stub_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            currency=allocated.currency,
        )

    if is_last_stub:
        return monthly_amount

    if days_active == days_total:
        return monthly_amount

    daily_rate = monthly_amount.amount / days_total
    stub_amount = daily_rate * days_active
    return Money(
        amount=stub_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        currency=allocated.currency,
    )


def deferred_revenue_schedule(
    obligations: list[PerformanceObligation],
    total_transaction_price: Money,
    start: date,
    end: date,
) -> list[DeferredEntry]:
    """Generate a monthly deferred revenue roll-forward.

    For each calendar month from *start* to *end* returns:

    * **beginning** — deferred carried from prior month
    * **additions** — new deferred from obligations starting this month
    * **recognized** — revenue amortised this month (stub months use
      :func:`stub_period_amortization`)
    * **ending** — ``beginning - recognized + additions``
    """
    if start > end:
        raise ValueError(f"start ({start}) must be on or before end ({end})")

    if not obligations:
        return []

    currency = total_transaction_price.currency
    total_standalone = _total_standalone_price(obligations)

    allocations: dict[str, Money] = {
        obl.obligation_id: _allocated_price(obl, total_standalone, total_transaction_price)
        for obl in obligations
    }

    entries: list[DeferredEntry] = []
    beginning_balance = zero(currency)

    cur_month = date(start.year, start.month, 1)
    end_month = date(end.year, end.month, 1)

    while cur_month <= end_month:
        month_end = date(
            cur_month.year,
            cur_month.month,
            _days_in_month(cur_month),
        )

        recognized = zero(currency)
        for obl in obligations:
            allocated = allocations[obl.obligation_id]
            if obl.satisfied_over_time:
                if obl.end_date is None:
                    continue
                if cur_month < date(obl.start_date.year, obl.start_date.month, 1):
                    continue
                if cur_month > date(obl.end_date.year, obl.end_date.month, 1):
                    continue

                total_months = _months_between(obl.start_date, obl.end_date)
                if total_months <= 0:
                    continue

                days_active = _days_active_in_month(obl, cur_month)
                if days_active <= 0:
                    continue

                monthly_amount = Money(
                    amount=(allocated.amount / total_months).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    ),
                    currency=currency,
                )

                days_total = _days_in_month(cur_month)
                if days_active == days_total:
                    recognized = recognized + monthly_amount
                else:
                    stub_amt = stub_period_amortization(
                        obl, total_transaction_price, cur_month
                    )
                    recognized = recognized + stub_amt

            else:
                if (
                    obl.end_date is not None
                    and obl.end_date.year == cur_month.year
                    and obl.end_date.month == cur_month.month
                ):
                    recognized = recognized + allocated

        additions = zero(currency)
        for obl in obligations:
            if (
                obl.start_date.year == cur_month.year
                and obl.start_date.month == cur_month.month
            ):
                additions = additions + allocations[obl.obligation_id]

        ending_balance = beginning_balance - recognized + additions

        entries.append(
            DeferredEntry(
                date=month_end,
                beginning_balance=beginning_balance,
                recognized=recognized,
                additions=additions,
                ending_balance=ending_balance,
            )
        )

        beginning_balance = ending_balance
        cur_month = _next_month(cur_month)

    return entries
