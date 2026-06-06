"""``customer`` subcommand — create, list, and show customers.

Examples::

    dinarledger customer create --name "Acme Corp" --currency KWD
    dinarledger customer list
    dinarledger customer show C-0001
"""

from __future__ import annotations

import argparse
from decimal import Decimal

from dinarledger.cli import store
from dinarledger.cli.formatters import format_money, output
from dinarledger.core.money import Money
from dinarledger.core.types import Customer


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``customer`` subcommand group."""
    parser = subparsers.add_parser("customer", help="Customer management")
    cust_sub = parser.add_subparsers(dest="customer_action")

    # create
    create_p = cust_sub.add_parser("create", help="Create a new customer")
    create_p.add_argument("--name", required=True, help="Customer name")
    create_p.add_argument("--currency", required=True, help="ISO 4217 currency code")
    create_p.add_argument("--credit-limit", type=float, default=None,
                          help="Credit limit amount")
    create_p.add_argument("--tax-exempt", action="store_true",
                          help="Mark customer as tax exempt")
    create_p.add_argument("--tax-jurisdiction", default="",
                          help="Tax jurisdiction code")
    create_p.set_defaults(handler=_cmd_create)

    # list
    list_p = cust_sub.add_parser("list", help="List all customers")
    list_p.set_defaults(handler=_cmd_list)

    # show
    show_p = cust_sub.add_parser("show", help="Show customer details")
    show_p.add_argument("customer_id", help="Customer ID")
    show_p.set_defaults(handler=_cmd_show)


# ── Command implementations ──────────────────────────────────────────────

def _cmd_create(args: argparse.Namespace) -> str:
    cust_id = store.next_customer_id()
    credit_limit = None
    if args.credit_limit is not None:
        credit_limit = Money(amount=Decimal(str(args.credit_limit)),
                             currency=args.currency.upper())

    customer = Customer(
        customer_id=cust_id,
        name=args.name,
        currency=args.currency,
        credit_limit=credit_limit,
        tax_exempt=args.tax_exempt,
        tax_jurisdiction=args.tax_jurisdiction,
    )
    store.customers[cust_id] = customer

    data = {
        "customer_id": cust_id,
        "name": customer.name,
        "currency": customer.currency,
    }
    if credit_limit is not None:
        data["credit_limit"] = format_money(credit_limit)

    return output(data, fmt=args.format)


def _cmd_list(args: argparse.Namespace) -> str:
    headers = ["ID", "Name", "Currency", "Credit Limit", "Tax Exempt"]
    rows = []
    for c in store.customers.values():
        cl = format_money(c.credit_limit) if c.credit_limit else "—"
        rows.append([c.customer_id, c.name, c.currency, cl,
                     "Yes" if c.tax_exempt else "No"])
    if not rows:
        return "No customers found."
    return output(
        data=[dict(zip(headers, r)) for r in rows],
        headers=headers, rows=rows, fmt=args.format,
    )


def _cmd_show(args: argparse.Namespace) -> str:
    customer = store.customers.get(args.customer_id)
    if customer is None:
        raise ValueError(f"Customer '{args.customer_id}' not found")

    data = {
        "customer_id": customer.customer_id,
        "name": customer.name,
        "currency": customer.currency,
        "credit_limit": format_money(customer.credit_limit) if customer.credit_limit else None,
        "tax_exempt": customer.tax_exempt,
        "tax_jurisdiction": customer.tax_jurisdiction or None,
    }
    return output(data, fmt=args.format)
