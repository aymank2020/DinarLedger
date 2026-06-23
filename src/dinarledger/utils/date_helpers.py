"""
dinarledger.utils.date_helpers — Date utility functions.

Business-day calculations, period-end helpers, and ISO date parsing.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta


def is_business_day(d: date) -> bool:
    """Return ``True`` if *d* falls on a weekday (Mon–Fri).

    Does **not** account for public holidays — that requires a
    jurisdiction-specific calendar.

    Parameters
    ----------
    d : date
        The date to check.

    Returns
    -------
    bool
        ``True`` when *d* is Monday through Friday.
    """
    return d.weekday() < 5


def add_business_days(d: date, n: int) -> date:
    """Add *n* business days to *d*, skipping weekends.

    A negative *n* subtracts business days.  Weekends are never counted
    as business days.

    Parameters
    ----------
    d : date
        The starting date.
    n : int
        Number of business days to add (may be negative).

    Returns
    -------
    date
        The resulting date after adding *n* business days.
    """
    if n == 0:
        return d

    direction = 1 if n > 0 else -1
    remaining = abs(n)
    current = d

    while remaining > 0:
        current += timedelta(days=direction)
        if is_business_day(current):
            remaining -= 1

    return current


def month_end(d: date) -> date:
    """Return the last day of the month containing *d*.

    Parameters
    ----------
    d : date
        Any date in the target month.

    Returns
    -------
    date
        The last calendar day of that month.

    Examples
    --------
    >>> month_end(date(2026, 2, 10))
    datetime.date(2026, 2, 28)
    >>> month_end(date(2024, 2, 1))  # leap year
    datetime.date(2024, 2, 29)
    """
    last_day = calendar.monthrange(d.year, d.month)[1]
    return date(d.year, d.month, last_day)


def quarter_end(d: date) -> date:
    """Return the last day of the calendar quarter containing *d*.

    Quarters are calendar-based: Q1 ends Mar 31, Q2 Jun 30, Q3 Sep 30,
    Q4 Dec 31.

    Parameters
    ----------
    d : date
        Any date in the target quarter.

    Returns
    -------
    date
        The last calendar day of that quarter.
    """
    quarter_month = {1: 3, 2: 6, 3: 9, 4: 12}
    q = (d.month - 1) // 3 + 1
    end_month = quarter_month[q]
    last_day = calendar.monthrange(d.year, end_month)[1]
    return date(d.year, end_month, last_day)


def year_end(d: date) -> date:
    """Return December 31 of the year containing *d*.

    Parameters
    ----------
    d : date
        Any date in the target year.

    Returns
    -------
    date
        December 31 of that year.
    """
    return date(d.year, 12, 31)


def parse_date(s: str) -> date:
    """Parse an ISO 8601 date string (``YYYY-MM-DD``).

    Parameters
    ----------
    s : str
        Date string in ISO format.

    Returns
    -------
    date
        The parsed date.

    Raises
    ------
    ValueError
        If *s* is not a valid ISO date string.
    """
    return date.fromisoformat(s)
