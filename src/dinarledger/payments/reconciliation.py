"""Bank reconciliation.

Matches DinarLedger payments to bank-statement entries by amount (within
a fixed monetary tolerance) and date proximity (within three business
days).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from dinarledger.core.money import Money
from dinarledger.core.types import Payment


# Weekend days for the simple business-day calendar (Mon=0 .. Sun=6).
_WEEKEND_DAYS = {5, 6}

# Maximum business-day distance for date matching.
_MAX_BUSINESS_DAY_DISTANCE = 3


def _is_business_day(d: date) -> bool:
    return d.weekday() not in _WEEKEND_DAYS


def _add_business_days(d: date, n: int) -> date:
    current = d
    added = 0
    while added < n:
        current += timedelta(days=1)
        if _is_business_day(current):
            added += 1
    return current


def _business_days_between(a: date, b: date) -> int:
    if a > b:
        a, b = b, a
    count = 0
    cur = a
    while cur <= b:
        if _is_business_day(cur):
            count += 1
        cur += timedelta(days=1)
    return count


@dataclass
class ReconciliationResult:
    """Result of a bank reconciliation run."""

    matched: list[tuple[str, str]] = field(default_factory=list)
    unmatched_payments: list[str] = field(default_factory=list)
    unmatched_bank: list[str] = field(default_factory=list)


def reconcile(
    payments: list[Payment],
    bank_entries: list[tuple[str, Money, date]],
    tolerance: Decimal = Decimal("0.05"),
) -> ReconciliationResult:
    """Match *payments* to *bank_entries* by amount and date proximity.

    A pair matches when:

    * ``abs(payment.amount − bank_amount) ≤ tolerance``
    * payment date and bank entry date are within three business days

    Greedy matching: each payment claims at most one bank entry and
    vice-versa, preferring the closest date when multiple amounts are in
    range. Payments without a ``paid_date`` are recorded as unmatched.
    """
    result = ReconciliationResult()

    if not payments and not bank_entries:
        return result

    matched_bank_indices: set[int] = set()
    bank_data: list[tuple[str, Money, date]] = list(bank_entries)

    for payment in payments:
        if payment.paid_date is None:
            result.unmatched_payments.append(payment.payment_id)
            continue

        best_idx: int | None = None
        best_day_distance: int | None = None

        for idx, (entry_id, bank_amount, bank_date) in enumerate(bank_data):
            if idx in matched_bank_indices:
                continue

            amount_diff = abs(payment.amount.amount - bank_amount.amount)
            if amount_diff > tolerance:
                continue

            day_distance = _business_days_between(payment.paid_date, bank_date)
            if day_distance > _MAX_BUSINESS_DAY_DISTANCE:
                continue

            if best_day_distance is None or day_distance < best_day_distance:
                best_idx = idx
                best_day_distance = day_distance

        if best_idx is not None:
            entry_id = bank_data[best_idx][0]
            result.matched.append((payment.payment_id, entry_id))
            matched_bank_indices.add(best_idx)
        else:
            result.unmatched_payments.append(payment.payment_id)

    for idx, (entry_id, _, _) in enumerate(bank_data):
        if idx not in matched_bank_indices:
            result.unmatched_bank.append(entry_id)

    return result
