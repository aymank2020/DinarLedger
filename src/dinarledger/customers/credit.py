"""
Customer credit-limit management.

Provides functions to check whether a customer's outstanding balance plus
a new charge stays within their credit limit, query their available
headroom, and suggest a revised limit based on payment history.

Outstanding balance is computed from invoices with status ``OPEN`` or
``OVERDUE``.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from dinarledger.core.money import Money, sum_money, zero
from dinarledger.core.types import Customer, Invoice, InvoiceStatus, Payment


# Window over which payment history is averaged when re-evaluating limits.
PAYMENT_HISTORY_DAYS = 180
PAYMENT_HISTORY_MONTHS = 6
LIMIT_MULTIPLIER = Decimal("1.5")
MIN_PAYMENTS_FOR_RECALC = 3


def check_credit_limit(
    customer: Customer,
    pending_invoices: list[Invoice],
    new_charge: Money,
) -> bool:
    """Return ``True`` if *new_charge* keeps the customer within their limit.

    Customers with ``credit_limit=None`` have unlimited credit.
    """
    if customer.credit_limit is None:
        return True

    outstanding = _sum_outstanding(pending_invoices, customer.currency)
    projected = outstanding + new_charge
    return projected <= customer.credit_limit


def available_credit(
    customer: Customer,
    pending_invoices: list[Invoice],
) -> Money:
    """Remaining credit headroom for *customer*.

    Returns ``Money(Decimal("Infinity"), currency)`` for unlimited credit.
    """
    if customer.credit_limit is None:
        return Money(amount=Decimal("Infinity"), currency=customer.currency)

    outstanding = _sum_outstanding(pending_invoices, customer.currency)
    return customer.credit_limit - outstanding


def recalculate_limit(
    customer: Customer,
    payment_history: list[Payment],
) -> Optional[Money]:
    """Suggest a new credit limit based on the last six months of payments.

    The suggestion is ``average_monthly_payment × 1.5``. Returns ``None``
    when fewer than three completed payments exist in the window.
    """
    cutoff = date.today() - timedelta(days=PAYMENT_HISTORY_DAYS)

    recent: list[Payment] = []
    for p in payment_history:
        if (
            p.paid_date is not None
            and p.paid_date >= cutoff
            and p.amount.currency == customer.currency
        ):
            recent.append(p)

    if len(recent) < MIN_PAYMENTS_FOR_RECALC:
        return None

    total = zero(customer.currency)
    for p in recent:
        total = total + p.amount

    avg_monthly_amount = total.amount / Decimal(PAYMENT_HISTORY_MONTHS)
    suggested_amount = avg_monthly_amount * LIMIT_MULTIPLIER
    return Money(
        amount=suggested_amount.quantize(Decimal("0.01")),
        currency=customer.currency,
    )


# ── Internal helpers ────────────────────────────────────────────────────────

def _sum_outstanding(invoices: list[Invoice], currency: str) -> Money:
    """Sum totals of OPEN and OVERDUE invoices in *currency*."""
    included_statuses = {InvoiceStatus.OPEN, InvoiceStatus.OVERDUE}
    totals: list[Money] = []
    for inv in invoices:
        if inv.status in included_statuses:
            inv_currency = inv._currency
            if inv_currency == currency:
                totals.append(inv.total)
    if not totals:
        return zero(currency)
    return sum_money(totals, currency)
