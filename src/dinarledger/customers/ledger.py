"""
Customer accounts-receivable ledger.

Models a customer's AR ledger as a sequence of debit/credit entries and
provides utilities to compute the running balance and aging buckets.
Aging buckets here are based on the ledger entry date, which captures
cash-flow timing for the ledger view.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

from dinarledger.core.money import Money, zero


@dataclass(frozen=True)
class ledger_entry:
    """A single line in the customer AR ledger.

    A debit increases the customer's balance (they owe more); a credit
    decreases it (they paid or received a credit note).
    """

    date: date
    debit: Optional[Money] = None
    credit: Optional[Money] = None
    reference: str = ""
    running_balance: Optional[Money] = None


# Aging-bucket labels.
_BUCKET_CURRENT = "current"
_BUCKET_1_30 = "1-30"
_BUCKET_31_60 = "31-60"
_BUCKET_61_90 = "61-90"
_BUCKET_90_PLUS = "90+"

_ALL_BUCKETS = [
    _BUCKET_CURRENT,
    _BUCKET_1_30,
    _BUCKET_31_60,
    _BUCKET_61_90,
    _BUCKET_90_PLUS,
]


def customer_ledger_balance(entries: list[ledger_entry]) -> Money:
    """Net AR balance from a list of ledger entries.

    Sum of all debits minus sum of all credits. Recomputed from the
    entries rather than relying on stored running totals.
    """
    if not entries:
        return zero("USD")

    currency = _infer_currency(entries)
    total = zero(currency)

    for entry in entries:
        if entry.debit is not None:
            total = total + entry.debit
        if entry.credit is not None:
            total = total - entry.credit

    return total


def aging_buckets(
    entries: list[ledger_entry],
    as_of: date,
) -> dict[str, Money]:
    """Group outstanding debit balances into aging buckets.

    Buckets are based on days elapsed between each entry's ``date`` and
    *as_of*: ``current`` (0 or future), ``1-30``, ``31-60``, ``61-90``,
    ``90+``.
    """
    currency = _infer_currency(entries) if entries else "USD"
    result: dict[str, Money] = {b: zero(currency) for b in _ALL_BUCKETS}

    for entry in entries:
        if entry.debit is None or entry.debit.is_zero():
            continue

        days_past = (as_of - entry.date).days
        bucket = _classify_days(days_past)
        result[bucket] = result[bucket] + entry.debit

    return result


# ── Internal helpers ────────────────────────────────────────────────────────

def _classify_days(days_past: int) -> str:
    if days_past <= 0:
        return _BUCKET_CURRENT
    if days_past <= 30:
        return _BUCKET_1_30
    if days_past <= 60:
        return _BUCKET_31_60
    if days_past <= 90:
        return _BUCKET_61_90
    return _BUCKET_90_PLUS


def _infer_currency(entries: list[ledger_entry]) -> str:
    """Best-effort currency inference from the first non-zero entry."""
    for entry in entries:
        if entry.debit is not None and not entry.debit.is_zero():
            return entry.debit.currency
        if entry.credit is not None and not entry.credit.is_zero():
            return entry.credit.currency
    return "USD"
