"""``subscription`` subcommand — create, cancel, reactivate, and change-plan.

Examples::

    dinarledger subscription create --customer C-0001 --plan PLAN-0001 --start 2025-01-01
    dinarledger subscription cancel SUB-0001 --date 2025-06-15 --immediate
    dinarledger subscription reactivate SUB-0001 --date 2025-06-20
    dinarledger subscription change-plan SUB-0001 --plan PLAN-0002 --date 2025-03-01
"""

from __future__ import annotations

import argparse
from datetime import date as date_type

from dinarledger.cli import store
from dinarledger.cli.formatters import format_money, output
from dinarledger.core.enums import SubscriptionStatus
from dinarledger.subscriptions.lifecycle import (
    cancel_subscription,
    change_plan,
    reactivate,
    subscribe,
)


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``subscription`` subcommand group."""
    parser = subparsers.add_parser("subscription", help="Subscription lifecycle")
    sub = parser.add_subparsers(dest="subscription_action")

    # create
    create_p = sub.add_parser("create", help="Create a subscription")
    create_p.add_argument("--customer", required=True, help="Customer ID")
    create_p.add_argument("--plan", required=True, help="Plan ID")
    create_p.add_argument("--start", required=True, help="Start date (YYYY-MM-DD)")
    create_p.add_argument("--seats", type=int, default=1, help="Number of seats")
    create_p.set_defaults(handler=_cmd_create)

    # cancel
    cancel_p = sub.add_parser("cancel", help="Cancel a subscription")
    cancel_p.add_argument("sub_id", help="Subscription ID")
    cancel_p.add_argument("--date", required=True, help="Cancel date (YYYY-MM-DD)")
    cancel_p.add_argument("--immediate", action="store_true",
                          help="Cancel immediately (vs end of period)")
    cancel_p.set_defaults(handler=_cmd_cancel)

    # reactivate
    react_p = sub.add_parser("reactivate", help="Reactivate a cancelled subscription")
    react_p.add_argument("sub_id", help="Subscription ID")
    react_p.add_argument("--date", required=True, help="Reactivation date (YYYY-MM-DD)")
    react_p.set_defaults(handler=_cmd_reactivate)

    # change-plan
    change_p = sub.add_parser("change-plan", help="Change the plan on a subscription")
    change_p.add_argument("sub_id", help="Subscription ID")
    change_p.add_argument("--plan", required=True, help="New plan ID")
    change_p.add_argument("--date", required=True, help="Change date (YYYY-MM-DD)")
    change_p.set_defaults(handler=_cmd_change_plan)


def _parse_date(s: str) -> date_type:
    """Parse a YYYY-MM-DD string into a date."""
    return date_type.fromisoformat(s)


# ── Command implementations ──────────────────────────────────────────────

def _cmd_create(args: argparse.Namespace) -> str:
    customer = store.customers.get(args.customer)
    if customer is None:
        raise ValueError(f"Customer '{args.customer}' not found")

    plan = store.plans.get(args.plan)
    if plan is None:
        raise ValueError(f"Plan '{args.plan}' not found")

    start = _parse_date(args.start)
    subscription = subscribe(
        customer_id=customer.customer_id,
        plan=plan,
        start_date=start,
        seat_count=args.seats,
    )
    store.subscriptions[subscription.sub_id] = subscription

    data = {
        "sub_id": subscription.sub_id,
        "customer_id": subscription.customer_id,
        "plan_id": subscription.plan.plan_id,
        "status": subscription.status.value,
        "start_date": str(subscription.start_date),
        "end_date": str(subscription.end_date) if subscription.end_date else "open-ended",
        "seats": subscription.seat_count,
    }
    return output(data, fmt=args.format)


def _cmd_cancel(args: argparse.Namespace) -> str:
    sub = store.subscriptions.get(args.sub_id)
    if sub is None:
        raise ValueError(f"Subscription '{args.sub_id}' not found")

    cancel_date = _parse_date(args.date)
    updated = cancel_subscription(sub, cancel_date, immediate=args.immediate)
    store.subscriptions[updated.sub_id] = updated

    data = {
        "sub_id": updated.sub_id,
        "status": updated.status.value,
        "cancelled_at": str(updated.cancelled_at) if updated.cancelled_at else None,
    }
    return output(data, fmt=args.format)


def _cmd_reactivate(args: argparse.Namespace) -> str:
    sub = store.subscriptions.get(args.sub_id)
    if sub is None:
        raise ValueError(f"Subscription '{args.sub_id}' not found")

    react_date = _parse_date(args.date)
    updated = reactivate(sub, react_date)
    store.subscriptions[updated.sub_id] = updated

    data = {
        "sub_id": updated.sub_id,
        "status": updated.status.value,
        "cancelled_at": str(updated.cancelled_at) if updated.cancelled_at else None,
    }
    return output(data, fmt=args.format)


def _cmd_change_plan(args: argparse.Namespace) -> str:
    sub = store.subscriptions.get(args.sub_id)
    if sub is None:
        raise ValueError(f"Subscription '{args.sub_id}' not found")

    new_plan = store.plans.get(args.plan)
    if new_plan is None:
        raise ValueError(f"Plan '{args.plan}' not found")

    change_date = _parse_date(args.date)
    updated, net_amount = change_plan(sub, new_plan, change_date)
    store.subscriptions[updated.sub_id] = updated

    data = {
        "sub_id": updated.sub_id,
        "new_plan_id": updated.plan.plan_id,
        "status": updated.status.value,
        "net_upgrade_amount": format_money(net_amount),
    }
    return output(data, fmt=args.format)
