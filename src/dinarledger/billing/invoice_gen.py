"""
Invoice generation.

Creates invoices from subscriptions with line items for the recurring
charge, seat overage, optional setup fee, and tax. Also exposes
``apply_adjustment`` and ``void_invoice`` for post-creation mutations.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional
from uuid import uuid4

from dinarledger.core.errors import InvoiceError
from dinarledger.core.money import Money
from dinarledger.core.types import (
    BillingPeriod,
    Invoice,
    InvoiceStatus,
    LineItem,
    Subscription,
    SubscriptionStatus,
    TaxRate,
)


# Default payment-term window in days (net-30).
DEFAULT_NET_DAYS = 30


# ── Public API ──────────────────────────────────────────────────────────────

def generate_invoice(
    subscription: Subscription,
    period: BillingPeriod,
    tax_rates: dict[str, TaxRate],
    *,
    tax_code: str = "",
    is_first_invoice: bool = False,
) -> Optional[Invoice]:
    """Generate an invoice for a subscription's billing period.

    Returns ``None`` for subscriptions that are not in ``ACTIVE`` state, or
    those whose ``cancelled_at`` precedes the period start (the cancellation
    has already taken effect).

    Line items produced:

    1. Subscription charge (``plan.base_price``).
    2. Seat overage when ``seat_count > 1``.
    3. Setup fee when ``is_first_invoice`` is ``True`` and the plan has one.
    4. Tax lines computed from *tax_code* and *tax_rates*.
    """
    if subscription.status != SubscriptionStatus.ACTIVE:
        return None

    if subscription.cancelled_at is not None:
        if subscription.cancelled_at < period.start_date:
            return None

    line_items: list[LineItem] = []

    # Recurring subscription charge
    line_items.append(
        LineItem(
            description=(
                f"Subscription: {subscription.plan.name} "
                f"({period.start_date.isoformat()} – {period.end_date.isoformat()})"
            ),
            amount=subscription.plan.base_price,
            tax_code=tax_code,
        )
    )

    # Per-seat overage above the included seat
    extra_seats = subscription.seat_count - 1
    if extra_seats > 0:
        line_items.append(
            LineItem(
                description=f"Seat overage: {extra_seats} additional seat(s)",
                amount=subscription.plan.base_price * extra_seats,
                tax_code=tax_code,
            )
        )

    # One-time setup fee (first invoice only)
    if is_first_invoice and subscription.plan.setup_fee is not None:
        line_items.append(
            LineItem(
                description=f"Setup fee: {subscription.plan.name}",
                amount=subscription.plan.setup_fee,
                tax_code=tax_code,
            )
        )

    line_items.extend(_compute_tax_lines(line_items, tax_rates, tax_code))

    today = date.today()
    return Invoice(
        invoice_id=str(uuid4()),
        customer_id=subscription.customer_id,
        issue_date=today,
        due_date=today + timedelta(days=DEFAULT_NET_DAYS),
        line_items=line_items,
        status=InvoiceStatus.DRAFT,
    )


def apply_adjustment(invoice: Invoice, adjustment: LineItem) -> Invoice:
    """Append an adjustment (credit or charge) line item to the invoice.

    Raises :class:`InvoiceError` if the invoice is ``VOIDED`` or ``PAID``.
    """
    if invoice.status == InvoiceStatus.VOIDED:
        raise InvoiceError(
            message="Cannot adjust a VOIDED invoice.",
            invoice_id=invoice.invoice_id,
            customer_id=invoice.customer_id,
        )
    if invoice.status == InvoiceStatus.PAID:
        raise InvoiceError(
            message="Cannot adjust a PAID invoice.",
            invoice_id=invoice.invoice_id,
            customer_id=invoice.customer_id,
        )

    return replace(invoice, line_items=list(invoice.line_items) + [adjustment])


def void_invoice(invoice: Invoice) -> Invoice:
    """Mark an invoice as ``VOIDED``.

    Paid invoices cannot be voided; issue a credit note instead.
    """
    if invoice.status == InvoiceStatus.PAID:
        raise InvoiceError(
            message="Cannot void a PAID invoice.  Issue a credit note instead.",
            invoice_id=invoice.invoice_id,
            customer_id=invoice.customer_id,
        )
    if invoice.status == InvoiceStatus.VOIDED:
        raise InvoiceError(
            message="Invoice is already VOIDED.",
            invoice_id=invoice.invoice_id,
            customer_id=invoice.customer_id,
        )

    return replace(invoice, status=InvoiceStatus.VOIDED)


# ── Internal helpers ────────────────────────────────────────────────────────

def _compute_tax_lines(
    charge_lines: list[LineItem],
    tax_rates: dict[str, TaxRate],
    default_tax_code: str,
) -> list[LineItem]:
    """Generate per-line tax entries from charge lines."""
    tax_lines: list[LineItem] = []

    for line in charge_lines:
        if line.is_tax:
            continue

        code = line.tax_code or default_tax_code
        if not code:
            continue

        tax_rate = tax_rates.get(code)
        if tax_rate is None:
            continue

        tax_amount = tax_rate.compute_tax(line.amount)
        if tax_amount.is_zero():
            continue

        tax_lines.append(
            LineItem(
                description=(
                    f"Tax ({tax_rate.code}: {tax_rate.description} "
                    f"@ {tax_rate.rate * Decimal('100')}%)"
                ),
                amount=tax_amount,
                tax_code=tax_rate.code,
                is_tax=True,
            )
        )

    return tax_lines
