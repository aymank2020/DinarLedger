"""Billing service — orchestrates invoice generation, payment processing,
void/credit operations, and aging reports.

Delegates to:
* ``dinarledger.billing.invoice_gen`` — invoice creation, void, adjustments
* ``dinarledger.payments.allocation`` — payment allocation across invoices
* ``dinarledger.reports.aging`` — AR aging buckets
* ``dinarledger.storage.base.Repository`` — persistence (injected)
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import uuid4

from dinarledger.core.enums import InvoiceStatus
from dinarledger.core.errors import (
    BillingError,
    DinarLedgerError,
    InvoiceError,
    PaymentAllocationError,
)
from dinarledger.core.money import Money, sum_money, zero
from dinarledger.core.types import (
    BillingPeriod,
    Invoice,
    LineItem,
    Payment,
    PaymentStatus,
    Subscription,
    TaxRate,
)
from dinarledger.billing.invoice_gen import (
    apply_adjustment as _apply_adjustment,
    generate_invoice as _generate_invoice,
    void_invoice as _void_invoice,
)
from dinarledger.payments.allocation import (
    allocate_payment as _allocate_payment,
    unallocated_amount as _unallocated_amount,
)
from dinarledger.reports.aging import aging_report as _aging_report
from dinarledger.storage.base import Repository


class BillingService:
    """Orchestrates the billing lifecycle.

    Parameters
    ----------
    invoice_repo : Repository[Invoice]
        Persistence for invoices.
    payment_repo : Repository[Payment]
        Persistence for payments.
    """

    def __init__(
        self,
        invoice_repo: Repository[Invoice],
        payment_repo: Repository[Payment],
    ) -> None:
        self._invoices = invoice_repo
        self._payments = payment_repo

    # ── Billing cycle ───────────────────────────────────────────────────────

    def run_billing_cycle(
        self,
        subscriptions: list[Subscription],
        period: BillingPeriod,
        tax_rates: dict[str, TaxRate],
    ) -> list[Invoice]:
        """Generate and persist invoices for all billable subscriptions.

        Only subscriptions in ``ACTIVE`` status are invoiced. Each
        generated invoice is persisted to the invoice repository and
        transitioned from ``DRAFT`` to ``OPEN``.

        Returns the list of created invoices (may be empty).
        """
        generated: list[Invoice] = []

        for sub in subscriptions:
            tax_code = sub.plan.tax_code or ""
            invoice = _generate_invoice(
                sub, period, tax_rates, tax_code=tax_code,
            )
            if invoice is None:
                continue

            # Transition DRAFT → OPEN
            open_invoice = replace(invoice, status=InvoiceStatus.OPEN)
            persisted = self._invoices.add(open_invoice)
            generated.append(persisted)

        return generated

    # ── Payment processing ──────────────────────────────────────────────────

    def process_payment(
        self,
        customer_id: str,
        amount: Money,
        invoices: list[Invoice],
        strategy: str = "oldest_first",
    ) -> tuple[Payment, list[tuple[str, Money]], Money]:
        """Record a payment, allocate across invoices, and persist.

        Parameters
        ----------
        customer_id : str
            The paying customer.
        amount : Money
            Total payment amount.
        invoices : list[Invoice]
            Outstanding invoices to allocate against.
        strategy : str
            ``"oldest_first"`` or ``"highest_first"``.

        Returns
        -------
        tuple[Payment, list[tuple[str, Money]], Money]
            The recorded payment, per-invoice allocations, and the
            unallocated (overpayment) remainder.
        """
        if amount.is_zero() or amount.is_negative():
            raise BillingError(
                f"Payment amount must be positive, got {amount}",
                customer_id=customer_id,
            )

        if not invoices:
            raise PaymentAllocationError(
                "No invoices provided for allocation",
                invoice_ids=[],
                unapplied_amount=amount,
            )

        allocations = _allocate_payment(amount, invoices, strategy)
        unallocated = _unallocated_amount(amount, allocations)

        payment = Payment(
            payment_id=f"pay-{uuid4().hex[:8]}",
            invoice_id=invoices[0].invoice_id,
            amount=amount,
            status=PaymentStatus.COMPLETED,
            paid_date=date.today(),
        )
        self._payments.add(payment)

        # Update invoice statuses based on allocations
        for inv_id, alloc_amount in allocations:
            if alloc_amount.is_zero():
                continue
            inv = self._invoices.get(inv_id)
            if inv is None:
                continue
            if alloc_amount >= inv.total:
                updated = replace(inv, status=InvoiceStatus.PAID)
            else:
                updated = replace(inv, status=InvoiceStatus.PARTIALLY_PAID)
            self._invoices.update(updated)

        return payment, allocations, unallocated

    # ── Void ────────────────────────────────────────────────────────────────

    def void_invoice(self, invoice_id: str) -> Invoice:
        """Void an invoice by ID.

        Raises
        ------
        InvoiceError
            If the invoice is already paid or not found.
        """
        inv = self._invoices.get(invoice_id)
        if inv is None:
            raise InvoiceError(
                f"Invoice '{invoice_id}' not found",
                invoice_id=invoice_id,
            )

        voided = _void_invoice(inv)
        self._invoices.update(voided)
        return voided

    # ── Credit note ─────────────────────────────────────────────────────────

    def apply_credit_note(
        self,
        invoice_id: str,
        amount: Money,
    ) -> Invoice:
        """Apply a credit note line to an invoice.

        The credit reduces the invoice balance. Only invoices that are
        ``OPEN`` or ``PARTIALLY_PAID`` can receive credit notes.
        """
        inv = self._invoices.get(invoice_id)
        if inv is None:
            raise InvoiceError(
                f"Invoice '{invoice_id}' not found",
                invoice_id=invoice_id,
            )

        if inv.status not in {InvoiceStatus.OPEN, InvoiceStatus.PARTIALLY_PAID}:
            raise InvoiceError(
                f"Cannot apply credit note to invoice in '{inv.status.value}' status",
                invoice_id=invoice_id,
                customer_id=inv.customer_id,
            )

        credit_line = LineItem(
            description=f"Credit note: {amount}",
            amount=-amount,
            item_type="credit",
        )

        adjusted = _apply_adjustment(inv, credit_line)
        self._invoices.update(adjusted)
        return adjusted

    # ── Aging report ────────────────────────────────────────────────────────

    def aging_report(
        self,
        invoices: list[Invoice],
        as_of: date,
    ) -> list[Any]:
        """Generate AR aging buckets from the given invoices.

        Delegates to :func:`dinarledger.reports.aging.aging_report`.
        """
        return _aging_report(invoices, as_of)
