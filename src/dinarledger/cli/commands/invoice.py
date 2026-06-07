"""``invoice`` subcommand — generate, void, list, and show invoices.

Examples::

    dinarledger invoice generate --sub SUB-0001 --start 2025-01-01 --end 2025-01-31
    dinarledger invoice void INV-xxxx
    dinarledger invoice list
    dinarledger invoice show INV-xxxx
"""

from __future__ import annotations

import argparse
from datetime import date as date_type

from dinarledger.cli import store
from dinarledger.cli.formatters import format_money, output
from dinarledger.billing.invoice_gen import generate_invoice, void_invoice
from dinarledger.core.enums import InvoiceStatus
from dinarledger.core.types import BillingPeriod, Invoice


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``invoice`` subcommand group."""
    parser = subparsers.add_parser("invoice", help="Invoice management")
    sub = parser.add_subparsers(dest="invoice_action")

    # generate
    gen_p = sub.add_parser("generate", help="Generate an invoice for a subscription")
    gen_p.add_argument("--sub", required=True, help="Subscription ID")
    gen_p.add_argument("--start", required=True, help="Period start (YYYY-MM-DD)")
    gen_p.add_argument("--end", required=True, help="Period end (YYYY-MM-DD)")
    gen_p.add_argument("--tax-code", default="", help="Tax code to apply")
    gen_p.add_argument("--first", action="store_true",
                        help="Mark as first invoice (include setup fee)")
    gen_p.set_defaults(handler=_cmd_generate)

    # void
    void_p = sub.add_parser("void", help="Void an invoice")
    void_p.add_argument("invoice_id", help="Invoice ID")
    void_p.set_defaults(handler=_cmd_void)

    # list
    list_p = sub.add_parser("list", help="List all invoices")
    list_p.set_defaults(handler=_cmd_list)

    # show
    show_p = sub.add_parser("show", help="Show invoice details")
    show_p.add_argument("invoice_id", help="Invoice ID")
    show_p.set_defaults(handler=_cmd_show)


def _parse_date(s: str) -> date_type:
    return date_type.fromisoformat(s)


def _invoice_to_dict(inv: Invoice) -> dict:
    """Convert an Invoice to a JSON-friendly dict."""
    return {
        "invoice_id": inv.invoice_id,
        "customer_id": inv.customer_id,
        "status": inv.status.value,
        "issue_date": str(inv.issue_date),
        "due_date": str(inv.due_date),
        "subtotal": format_money(inv.subtotal),
        "total_tax": format_money(inv.total_tax),
        "total": format_money(inv.total),
        "line_items": [
            {
                "description": li.description,
                "amount": format_money(li.amount),
                "is_tax": li.is_tax,
            }
            for li in inv.line_items
        ],
    }


# ── Command implementations ──────────────────────────────────────────────

def _cmd_generate(args: argparse.Namespace) -> str:
    sub = store.subscriptions.get(args.sub)
    if sub is None:
        raise ValueError(f"Subscription '{args.sub}' not found")

    period = BillingPeriod(
        start_date=_parse_date(args.start),
        end_date=_parse_date(args.end),
    )

    invoice = generate_invoice(
        subscription=sub,
        period=period,
        tax_rates=store.tax_rates,
        tax_code=args.tax_code,
        is_first_invoice=args.first,
    )

    if invoice is None:
        raise ValueError(
            f"Cannot generate invoice for subscription '{args.sub}' "
            f"(status={sub.status.value})"
        )

    store.invoices[invoice.invoice_id] = invoice

    return output(_invoice_to_dict(invoice), fmt=args.format)


def _cmd_void(args: argparse.Namespace) -> str:
    inv = store.invoices.get(args.invoice_id)
    if inv is None:
        raise ValueError(f"Invoice '{args.invoice_id}' not found")

    updated = void_invoice(inv)
    store.invoices[updated.invoice_id] = updated

    data = {
        "invoice_id": updated.invoice_id,
        "status": updated.status.value,
    }
    return output(data, fmt=args.format)


def _cmd_list(args: argparse.Namespace) -> str:
    headers = ["ID", "Customer", "Status", "Issue Date", "Due Date", "Total"]
    rows = []
    for inv in store.invoices.values():
        rows.append([
            inv.invoice_id[:8] + "…",
            inv.customer_id,
            inv.status.value,
            str(inv.issue_date),
            str(inv.due_date),
            format_money(inv.total),
        ])
    if not rows:
        return "No invoices found."
    return output(
        data=[dict(zip(headers, r)) for r in rows],
        headers=headers, rows=rows, fmt=args.format,
    )


def _cmd_show(args: argparse.Namespace) -> str:
    inv = store.invoices.get(args.invoice_id)
    if inv is None:
        raise ValueError(f"Invoice '{args.invoice_id}' not found")
    return output(_invoice_to_dict(inv), fmt=args.format)
