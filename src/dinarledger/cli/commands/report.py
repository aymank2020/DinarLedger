"""``report`` subcommand — aging, MRR, and deferred revenue reports.

Examples::

    dinarledger report aging --as-of 2025-03-15
    dinarledger report mrr --month 2025-03
    dinarledger report deferred --obligations obl.json --price 1200.00 USD --as-of 2025-02-15
"""

from __future__ import annotations

import argparse
import json
from datetime import date as date_type
from decimal import Decimal

from dinarledger.cli import store
from dinarledger.cli.formatters import format_money, output
from dinarledger.core.money import Money
from dinarledger.core.types import BillingPeriod
from dinarledger.reports.aging import aging_report
from dinarledger.reports.mrr import calculate_mrr
from dinarledger.reports.deferred_schedule import deferred_waterfall
from dinarledger.revenue.recognition import PerformanceObligation


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``report`` subcommand group."""
    parser = subparsers.add_parser("report", help="Financial reports")
    sub = parser.add_subparsers(dest="report_action")

    # aging
    aging_p = sub.add_parser("aging", help="AR aging report")
    aging_p.add_argument("--as-of", required=True, help="As-of date (YYYY-MM-DD)")
    aging_p.set_defaults(handler=_cmd_aging)

    # mrr
    mrr_p = sub.add_parser("mrr", help="Monthly recurring revenue report")
    mrr_p.add_argument("--month", required=True, help="Month (YYYY-MM)")
    mrr_p.set_defaults(handler=_cmd_mrr)

    # deferred
    def_p = sub.add_parser("deferred", help="Deferred revenue waterfall report")
    def_p.add_argument("--obligations", required=True,
                       help="JSON file with obligation definitions")
    def_p.add_argument("--price", required=True, type=float,
                       help="Total transaction price")
    def_p.add_argument("--currency", required=True, help="Currency code")
    def_p.add_argument("--start", required=True, help="Start date (YYYY-MM-DD)")
    def_p.add_argument("--months", type=int, default=12, help="Number of months")
    def_p.set_defaults(handler=_cmd_deferred)


def _parse_date(s: str) -> date_type:
    return date_type.fromisoformat(s)


def _load_obligations(path: str, currency: str) -> list[PerformanceObligation]:
    """Load obligations from a JSON file."""
    with open(path) as f:
        data = json.load(f)
    obligations = []
    for item in data:
        obl = PerformanceObligation(
            obligation_id=item["id"],
            description=item["description"],
            standalone_price=Money(
                amount=Decimal(str(item["standalone_price"])),
                currency=currency,
            ),
            satisfied_over_time=item["satisfied_over_time"],
            start_date=date_type.fromisoformat(item["start_date"]),
            end_date=date_type.fromisoformat(item["end_date"]) if item.get("end_date") else None,
        )
        obligations.append(obl)
    return obligations


# ── Command implementations ──────────────────────────────────────────────

def _cmd_aging(args: argparse.Namespace) -> str:
    as_of = _parse_date(args.as_of)
    invoices = list(store.invoices.values())

    if not invoices:
        return "No invoices to report on."

    buckets = aging_report(invoices, as_of)
    headers = ["Bucket", "Total", "Invoices"]
    rows = [
        [b.label, format_money(b.total), str(b.invoice_count)]
        for b in buckets
    ]
    data = {
        "as_of": str(as_of),
        "buckets": [
            {"label": b.label, "total": format_money(b.total),
             "invoice_count": b.invoice_count}
            for b in buckets
        ],
    }
    return output(data, headers=headers, rows=rows, fmt=args.format)


def _cmd_mrr(args: argparse.Namespace) -> str:
    # Parse YYYY-MM to a date (first of month)
    parts = args.month.split("-")
    month_date = date_type(int(parts[0]), int(parts[1]), 1)

    subscriptions = list(store.subscriptions.values())
    plans = store.plans

    if not subscriptions:
        return "No subscriptions to report on."

    breakdown = calculate_mrr(subscriptions, plans, month_date)
    data = {
        "month": str(breakdown.month),
        "new_mrr": format_money(breakdown.new_mrr),
        "expansion_mrr": format_money(breakdown.expansion_mrr),
        "contraction_mrr": format_money(breakdown.contraction_mrr),
        "churn_mrr": format_money(breakdown.churn_mrr),
        "net_mrr": format_money(breakdown.net_mrr),
        "total_mrr": format_money(breakdown.total_mrr),
    }
    return output(data, fmt=args.format)


def _cmd_deferred(args: argparse.Namespace) -> str:
    obligations = _load_obligations(args.obligations, args.currency)
    total_price = Money(amount=Decimal(str(args.price)), currency=args.currency)
    start = _parse_date(args.start)

    entries = deferred_waterfall(obligations, total_price, start, months=args.months)
    headers = ["Month", "Beginning", "Additions", "Recognized", "Ending"]
    rows = [
        [str(e.month), format_money(e.beginning), format_money(e.additions),
         format_money(e.recognized), format_money(e.ending)]
        for e in entries
    ]
    data = {
        "waterfall": [
            {"month": str(e.month), "beginning": format_money(e.beginning),
             "additions": format_money(e.additions),
             "recognized": format_money(e.recognized),
             "ending": format_money(e.ending)}
            for e in entries
        ],
    }
    return output(data, headers=headers, rows=rows, fmt=args.format)
