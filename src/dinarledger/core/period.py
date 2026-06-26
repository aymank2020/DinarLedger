"""
dinarledger.core.period — billing period and proration utilities.

Date-arithmetic helpers for generating billing periods, computing
proration fractions, and deriving stub periods from mid-cycle effective
dates. Periods are inclusive on both ends.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import List

from .errors import InvalidParameterError
from .types import BillingPeriod


# ---------------------------------------------------------------------------
# Month helpers
# ---------------------------------------------------------------------------

def days_in_month(year: int, month: int) -> int:
    """Number of days in the given *year* and *month*.

    Handles leap years via :func:`calendar.monthrange`.
    """
    if not 1 <= month <= 12:
        raise InvalidParameterError(
            "month", message=f"month must be 1–12, got {month}"
        )
    return calendar.monthrange(year, month)[1]


def days_in_period(start: date, end: date) -> int:
    """Number of days in the inclusive interval ``[start, end]``.

    Returns 0 when *start* is after *end*.
    """
    if start > end:
        return 0
    return (end - start).days + 1


# ---------------------------------------------------------------------------
# Billing period generation
# ---------------------------------------------------------------------------

_CYCLE_MONTHS = {"monthly": 1, "quarterly": 3, "annual": 12}


def billing_periods(start: date, cycles: int, cycle: str) -> List[BillingPeriod]:
    """Generate consecutive billing periods starting from *start*.

    Each period begins on the same day-of-month as *start* (clamped to
    the last day of the target month when that day does not exist) and
    ends on the day before the next period starts.
    """
    if cycles < 1:
        raise InvalidParameterError(
            "cycles", message=f"cycles must be >= 1, got {cycles}"
        )
    if cycle not in _CYCLE_MONTHS:
        raise InvalidParameterError(
            "cycle",
            message=f"cycle must be one of {list(_CYCLE_MONTHS)}, got '{cycle}'",
        )

    month_step = _CYCLE_MONTHS[cycle]
    periods: list[BillingPeriod] = []
    current_start = start

    for _ in range(cycles):
        next_start = _advance_months(current_start, month_step)
        current_end = next_start - timedelta(days=1)

        periods.append(
            BillingPeriod(start_date=current_start, end_date=current_end)
        )
        current_start = next_start

    return periods


def _advance_months(dt: date, months: int) -> date:
    """Return *dt* shifted forward by *months* calendar months.

    Day-of-month is clamped to the last day of the target month.
    """
    target_month = dt.month + months
    target_year = dt.year + (target_month - 1) // 12
    target_month = ((target_month - 1) % 12) + 1

    max_day = days_in_month(target_year, target_month)
    target_day = min(dt.day, max_day)

    return date(target_year, target_month, target_day)


# ---------------------------------------------------------------------------
# Proration
# ---------------------------------------------------------------------------

# 10 decimal places is more than enough for billing-grade precision while
# avoiding floating-point representation issues.
_PRORATION_PRECISION = Decimal("0.0000000001")


def proration_fraction(
    period: BillingPeriod,
    active_start: date,
    active_end: date,
) -> Decimal:
    """Fraction of *period* that overlaps the active interval.

    Equals ``days_active / days_in_period`` with both counts taken
    inclusively. Dates outside *period* are clamped to its boundaries;
    a non-overlapping interval yields zero.
    """
    eff_start = max(active_start, period.start_date)
    eff_end = min(active_end, period.end_date)

    if eff_start > eff_end:
        return Decimal("0")

    days_active = (eff_end - eff_start).days + 1
    days_in_p = (period.end_date - period.start_date).days + 1

    if days_active == days_in_p:
        return Decimal("1")

    fraction = Decimal(days_active) / Decimal(days_in_p)
    return fraction.quantize(_PRORATION_PRECISION, rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------------------
# Stub period
# ---------------------------------------------------------------------------

def stub_period(
    period: BillingPeriod,
    effective_date: date,
) -> BillingPeriod | None:
    """Remaining portion of *period* starting from *effective_date*.

    Returns the full period when *effective_date* is at or before the
    period start, and ``None`` when it is past the period end.
    """
    if effective_date >= period.end_date:
        return None

    stub_start = max(effective_date, period.start_date)
    return BillingPeriod(start_date=stub_start, end_date=period.end_date)
