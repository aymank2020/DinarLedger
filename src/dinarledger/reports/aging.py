"""AR aging report — groups unpaid invoices by days past due."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from dinarledger.core.enums import InvoiceStatus
from dinarledger.core.money import Money, zero as _zero
from dinarledger.core.types import Invoice


@dataclass(frozen=True, slots=True)
class AgingBucket:
    """A single aging bucket with label, total outstanding, and count."""

    label: str
    total: Money
    invoice_count: int


# Bucket definitions ordered for display.
_BUCKET_DEFS: list[tuple[str, int]] = [
    ("Current", -999),
    ("1-30", 1),
    ("31-60", 31),
    ("61-90", 61),
    ("90+", 91),
]


def aging_report(
    invoices: list[Invoice],
    as_of: date,
) -> list[AgingBucket]:
    """Group unpaid invoices into aging buckets by ``due_date``.

    Buckets are ``Current`` (not yet due), ``1-30``, ``31-60``, ``61-90``,
    and ``90+`` days past due. PAID and VOIDED invoices are excluded.
    """
    currency = "USD"
    for inv in invoices:
        if inv.line_items:
            currency = inv.line_items[0].amount.currency
            break

    totals: dict[str, Money] = {label: _zero(currency) for label, _ in _BUCKET_DEFS}
    counts: dict[str, int] = {label: 0 for label, _ in _BUCKET_DEFS}

    eligible_statuses = {InvoiceStatus.OPEN, InvoiceStatus.DRAFT, InvoiceStatus.OVERDUE}

    for inv in invoices:
        if inv.status not in eligible_statuses:
            continue
        days_past_due = (as_of - inv.due_date).days
        label = _bucket_for(days_past_due)
        totals[label] = totals[label] + inv.total
        counts[label] += 1

    return [
        AgingBucket(label=label, total=totals[label], invoice_count=counts[label])
        for label, _ in _BUCKET_DEFS
    ]


def _bucket_for(days_past_due: int) -> str:
    """Map a days-past-due count to its bucket label."""
    if days_past_due < 1:
        return "Current"
    if days_past_due <= 30:
        return "1-30"
    if days_past_due <= 60:
        return "31-60"
    if days_past_due <= 90:
        return "61-90"
    return "90+"
