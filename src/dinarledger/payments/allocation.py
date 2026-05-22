"""Payment allocation across invoices.

Allocates a payment amount across a list of outstanding invoices using
one of two strategies:

* ``oldest_first`` — invoices ordered by ``due_date`` ascending.
* ``highest_first`` — invoices ordered by ``total`` descending.

Each invoice is allocated up to its ``invoice.total`` (the sum of line
items including tax).
"""

from __future__ import annotations

from decimal import Decimal

from dinarledger.core.money import Money, zero
from dinarledger.core.types import Invoice, InvoiceStatus


def allocate_payment(
    payment: Money,
    invoices: list[Invoice],
    strategy: str = "oldest_first",
) -> list[tuple[str, Money]]:
    """Allocate *payment* across *invoices* using the given *strategy*.

    Invoices are processed in strategy order and each receives up to its
    outstanding amount before the next invoice is considered.

    Returns a list of ``(invoice_id, allocated_amount)`` tuples covering
    every input invoice (zero allocation included for completeness).
    """
    if strategy not in ("oldest_first", "highest_first"):
        raise ValueError(
            f"Unknown strategy {strategy!r}; expected 'oldest_first' or 'highest_first'"
        )

    if not invoices:
        return []

    sorted_invoices = _sort_invoices(invoices, strategy)

    remaining = payment.amount
    allocations: list[tuple[str, Money]] = []

    for inv in sorted_invoices:
        if remaining <= Decimal("0"):
            allocations.append((inv.invoice_id, zero(payment.currency)))
            continue

        outstanding = inv.total.amount
        to_allocate = min(outstanding, remaining)
        allocations.append(
            (inv.invoice_id, Money(amount=to_allocate, currency=payment.currency))
        )
        remaining -= to_allocate

    return allocations


def _sort_invoices(invoices: list[Invoice], strategy: str) -> list[Invoice]:
    """Return *invoices* sorted according to the chosen *strategy*."""
    if strategy == "oldest_first":
        return sorted(invoices, key=lambda inv: inv.due_date)

    if strategy == "highest_first":
        return sorted(invoices, key=lambda inv: inv.total.amount, reverse=True)

    return invoices


def unallocated_amount(
    payment: Money,
    allocations: list[tuple[str, Money]],
) -> Money:
    """Return ``payment - sum(allocated amounts)``."""
    total_allocated = zero(payment.currency)
    for _, allocated in allocations:
        total_allocated = total_allocated + allocated
    return payment - total_allocated
