"""``payment`` subcommand — record, allocate, and reconcile payments.

Examples::

    dinarledger payment record --invoice INV-xxxx --amount 100.00 --currency USD
    dinarledger payment allocate --amount 250.00 --currency USD --strategy oldest_first
    dinarledger payment reconcile --bank-file bank_entries.json
"""

from __future__ import annotations

import argparse
from datetime import date as date_type
from decimal import Decimal

from dinarledger.cli import store
from dinarledger.cli.formatters import format_money, output
from dinarledger.core.enums import InvoiceStatus
from dinarledger.core.money import Money
from dinarledger.core.types import Payment, PaymentStatus
from dinarledger.payments.allocation import allocate_payment, unallocated_amount
from dinarledger.payments.reconciliation import reconcile


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``payment`` subcommand group."""
    parser = subparsers.add_parser("payment", help="Payment management")
    sub = parser.add_subparsers(dest="payment_action")

    # record
    rec_p = sub.add_parser("record", help="Record a payment against an invoice")
    rec_p.add_argument("--invoice", required=True, help="Invoice ID")
    rec_p.add_argument("--amount", required=True, type=float, help="Payment amount")
    rec_p.add_argument("--currency", required=True, help="Payment currency")
    rec_p.add_argument("--date", default=None, help="Payment date (YYYY-MM-DD)")
    rec_p.add_argument("--reference", default="", help="Payment reference")
    rec_p.set_defaults(handler=_cmd_record)

    # allocate
    alloc_p = sub.add_parser("allocate", help="Allocate payment across invoices")
    alloc_p.add_argument("--amount", required=True, type=float,
                         help="Total payment amount")
    alloc_p.add_argument("--currency", required=True, help="Payment currency")
    alloc_p.add_argument("--strategy", default="oldest_first",
                         choices=["oldest_first", "highest_first"],
                         help="Allocation strategy")
    alloc_p.set_defaults(handler=_cmd_allocate)

    # reconcile
    recon_p = sub.add_parser("reconcile", help="Reconcile payments with bank entries")
    recon_p.add_argument("--tolerance", type=float, default=0.05,
                         help="Amount tolerance for matching")
    recon_p.set_defaults(handler=_cmd_reconcile)


def _parse_date(s: str | None) -> date_type | None:
    if s is None:
        return None
    return date_type.fromisoformat(s)


# ── Command implementations ──────────────────────────────────────────────

def _cmd_record(args: argparse.Namespace) -> str:
    inv = store.invoices.get(args.invoice)
    if inv is None:
        raise ValueError(f"Invoice '{args.invoice}' not found")

    pay_id = store.next_payment_id()
    amount = Money(amount=Decimal(str(args.amount)), currency=args.currency)
    paid_date = _parse_date(args.date)

    payment = Payment(
        payment_id=pay_id,
        invoice_id=inv.invoice_id,
        amount=amount,
        status=PaymentStatus.COMPLETED,
        paid_date=paid_date,
        reference=args.reference,
    )
    store.payments[pay_id] = payment

    data = {
        "payment_id": pay_id,
        "invoice_id": inv.invoice_id[:8] + "…",
        "amount": format_money(amount),
        "status": payment.status.value,
        "paid_date": str(paid_date) if paid_date else None,
    }
    return output(data, fmt=args.format)


def _cmd_allocate(args: argparse.Namespace) -> str:
    payment = Money(amount=Decimal(str(args.amount)), currency=args.currency)

    # Collect outstanding (non-VOIDED, non-PAID) invoices
    outstanding = [
        inv for inv in store.invoices.values()
        if inv.status not in (InvoiceStatus.VOIDED, InvoiceStatus.PAID)
    ]

    if not outstanding:
        return "No outstanding invoices to allocate against."

    allocations = allocate_payment(payment, outstanding, strategy=args.strategy)
    unallocated = unallocated_amount(payment, allocations)

    headers = ["Invoice ID", "Allocated"]
    rows = []
    for inv_id, amt in allocations:
        rows.append([inv_id[:8] + "…", format_money(amt)])

    data = {
        "total_payment": format_money(payment),
        "strategy": args.strategy,
        "allocations": [
            {"invoice_id": inv_id, "allocated": format_money(amt)}
            for inv_id, amt in allocations
        ],
        "unallocated": format_money(unallocated),
    }
    return output(data, headers=headers, rows=rows, fmt=args.format)


def _cmd_reconcile(args: argparse.Namespace) -> str:
    payments_list = list(store.payments.values())

    if not payments_list:
        return "No payments recorded to reconcile."

    # Build bank entries from invoices (simulated)
    bank_entries = []
    for inv in store.invoices.values():
        if inv.status == InvoiceStatus.PAID:
            bank_entries.append((f"BANK-{inv.invoice_id[:6]}", inv.total, inv.due_date))

    if not bank_entries:
        return "No bank entries to reconcile against."

    result = reconcile(
        payments=payments_list,
        bank_entries=bank_entries,
        tolerance=Decimal(str(args.tolerance)),
    )

    data = {
        "matched": result.matched,
        "unmatched_payments": result.unmatched_payments,
        "unmatched_bank": result.unmatched_bank,
    }
    return output(data, fmt=args.format)
