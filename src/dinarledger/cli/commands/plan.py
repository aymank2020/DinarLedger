"""``plan`` subcommand — create and list billing plans.

Examples::

    dinarledger plan create --name "Pro" --price 50.00 --currency USD --cycle monthly
    dinarledger plan list
"""

from __future__ import annotations

import argparse
from decimal import Decimal

from dinarledger.cli import store
from dinarledger.cli.formatters import format_money, output
from dinarledger.core.money import Money
from dinarledger.core.types import Plan


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``plan`` subcommand group."""
    parser = subparsers.add_parser("plan", help="Plan management")
    plan_sub = parser.add_subparsers(dest="plan_action")

    # create
    create_p = plan_sub.add_parser("create", help="Create a new plan")
    create_p.add_argument("--name", required=True, help="Plan name")
    create_p.add_argument("--price", required=True, type=float,
                          help="Base price amount")
    create_p.add_argument("--currency", required=True, help="ISO 4217 currency")
    create_p.add_argument("--cycle", required=True,
                          choices=["monthly", "quarterly", "annual"],
                          help="Billing cycle")
    create_p.add_argument("--setup-fee", type=float, default=None,
                          help="One-time setup fee")
    create_p.add_argument("--trial-days", type=int, default=0,
                          help="Number of trial days")
    create_p.add_argument("--seats-included", type=int, default=1,
                          help="Seats included in base price")
    create_p.set_defaults(handler=_cmd_create)

    # list
    list_p = plan_sub.add_parser("list", help="List all plans")
    list_p.set_defaults(handler=_cmd_list)


def _cmd_create(args: argparse.Namespace) -> str:
    plan_id = store.next_plan_id()
    base_price = Money(amount=Decimal(str(args.price)), currency=args.currency)
    setup_fee = None
    if args.setup_fee is not None:
        setup_fee = Money(amount=Decimal(str(args.setup_fee)), currency=args.currency)

    plan = Plan(
        plan_id=plan_id,
        name=args.name,
        base_price=base_price,
        billing_cycle=args.cycle,
        setup_fee=setup_fee,
        trial_days=args.trial_days,
        seats_included=args.seats_included,
    )
    store.plans[plan_id] = plan

    data = {
        "plan_id": plan_id,
        "name": plan.name,
        "base_price": format_money(plan.base_price),
        "billing_cycle": plan.billing_cycle,
    }
    return output(data, fmt=args.format)


def _cmd_list(args: argparse.Namespace) -> str:
    headers = ["ID", "Name", "Base Price", "Cycle", "Trial Days", "Seats"]
    rows = []
    for p in store.plans.values():
        rows.append([
            p.plan_id, p.name, format_money(p.base_price),
            p.billing_cycle, str(p.trial_days), str(p.seats_included),
        ])
    if not rows:
        return "No plans found."
    return output(
        data=[dict(zip(headers, r)) for r in rows],
        headers=headers, rows=rows, fmt=args.format,
    )
