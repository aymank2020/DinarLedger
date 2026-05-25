"""Deferred revenue waterfall schedule.

Generates a month-by-month waterfall in the form
``beginning + additions − recognised = ending``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from dinarledger.core.money import Money
from dinarledger.revenue.deferred import deferred_revenue_schedule
from dinarledger.revenue.recognition import PerformanceObligation


@dataclass(frozen=True, slots=True)
class WaterfallEntry:
    """One month's row in the deferred revenue waterfall."""

    month: date
    beginning: Money
    additions: Money
    recognized: Money
    ending: Money


def deferred_waterfall(
    obligations: list[PerformanceObligation],
    total_price: Money,
    start: date,
    months: int = 12,
) -> list[WaterfallEntry]:
    """Generate a monthly deferred revenue waterfall.

    Returns one ``WaterfallEntry`` per calendar month in chronological
    order, capped at *months* entries.
    """
    if not obligations:
        return []

    end = start
    for obl in obligations:
        if obl.end_date is not None and obl.end_date > end:
            end = obl.end_date

    schedule = deferred_revenue_schedule(
        obligations, total_price, start, end,
    )

    entries: list[WaterfallEntry] = []
    for entry in schedule:
        month_first = date(entry.date.year, entry.date.month, 1)
        entries.append(
            WaterfallEntry(
                month=month_first,
                beginning=entry.beginning_balance,
                additions=entry.additions,
                recognized=entry.recognized,
                ending=entry.ending_balance,
            )
        )

    return entries[:months]
