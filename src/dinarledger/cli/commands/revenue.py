"""``revenue`` subcommand — recognize, deferred, and waterfall commands.

Examples::

    dinarledger revenue recognize --obligations obl.json --price 1200.00 USD --period-start 2025-01-01 --period-end 2025-03-31
    dinarledger revenue deferred --obligations obl.json --price 1200.00 USD --as-of 2025-02-15
    dinarledger revenue waterfall --obligations obl.json --price 1200.00 USD --start 2025-01-01 --months 6
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
from dinarledger.revenue.recognition import (
    PerformanceObligation,
    calculate_deferred,
    recognize_revenue,
)
from dinarledger.reports.deferred_schedule import deferred_waterfall


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``revenue`` subcommand group."""
    parser = subparsers.add_parser("revenue", help="Revenue recognition")
    sub = parser.add_subparsers(dest="revenue_action")

    # recognize
    rec_p = sub.add_parser("recognize", help="Recognize revenue for a period")
    rec_p.add_argument("--obligations", required=True,
                       help="JSON file with obligation definitions")
    rec_p.add_argument("--price", required=True, type=float,
                       help="Total transaction price")
    rec_p.add_argument("--currency", required=True, help="Currency code")
    rec_p.add_argument("--period-start", required=True, help="Period start (YYYY-MM-DD)")
    rec_p.add_argument("--period-end", required=True, help="Period end (YYYY-MM-DD)")
    rec_p.set_defaults(handler=_cmd_recognize)

    # deferred
    def_p = sub.add_parser("deferred", help="Calculate deferred revenue as of a date")
    def_p.add_argument("--obligations", required=True,
                       help="JSON file with obligation definitions")
    def_p.add_argument("--price", required=True, type=float,
                       help="Total transaction price")
    def_p.add_argument("--currency", required=True, help="Currency code")
    def_p.add_argument("--as-of", required=True, help="As-of date (YYYY-MM-DD)")
    def_p.set_defaults(handler=_cmd_deferred)

    # waterfall
    wf_p = sub.add_parser("waterfall", help="Generate deferred revenue waterfall")
    wf_p.add_argument("--obligations", required=True,
                      help="JSON file with obligation definitions")
    wf_p.add_argument("--price", required=True, type=float,
                      help="Total transaction price")
    wf_p.add_argument("--currency", required=True, help="Currency code")
    wf_p.add_argument("--start", required=True, help="Start date (YYYY-MM-DD)")
    wf_p.add_argument("--months", type=int, default=12, help="Number of months")
    wf_p.set_defaults(handler=_cmd_waterfall)


def _load_obligations(path: str, currency: str) -> list[PerformanceObligation]:
    """Load obligations from a JSON file.

    Expected format: list of dicts with keys:
    id, description, standalone_price, satisfied_over_time,
    start_date, end_date (optional).
    """
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


def _parse_date(s: str) -> date_type:
    return date_type.fromisoformat(s)


# ── Command implementations ──────────────────────────────────────────────

def _cmd_recognize(args: argparse.Namespace) -> str:
    obligations = _load_obligations(args.obligations, args.currency)
    total_price = Money(amount=Decimal(str(args.price)), currency=args.currency)
    period = BillingPeriod(
        start_date=_parse_date(args.period_start),
        end_date=_parse_date(args.period_end),
    )

    results = recognize_revenue(obligations, total_price, period)
    data = {
        "period": f"{period.start_date}..{period.end_date}",
        "results": [
            {"obligation_id": obl_id, "recognized": format_money(amt)}
            for obl_id, amt in results
        ],
    }
    return output(data, fmt=args.format)


def _cmd_deferred(args: argparse.Namespace) -> str:
    obligations = _load_obligations(args.obligations, args.currency)
    total_price = Money(amount=Decimal(str(args.price)), currency=args.currency)
    as_of = _parse_date(args.as_of)

    deferred = calculate_deferred(obligations, total_price, as_of)
    data = {
        "as_of": str(as_of),
        "deferred_revenue": format_money(deferred),
    }
    return output(data, fmt=args.format)


def _cmd_waterfall(args: argparse.Namespace) -> str:
    obligations = _load_obligations(args.obligations, args.currency)
    total_price = Money(amount=Decimal(str(args.price)), currency=args.currency)
    start = _parse_date(args.start)

    entries = deferred_waterfall(obligations, total_price, start, months=args.months)
    headers = ["Month", "Beginning", "Additions", "Recognized", "Ending"]
    rows = []
    for e in entries:
        rows.append([
            str(e.month), format_money(e.beginning),
            format_money(e.additions), format_money(e.recognized),
            format_money(e.ending),
        ])
    data = {
        "waterfall": [
            {
                "month": str(e.month),
                "beginning": format_money(e.beginning),
                "additions": format_money(e.additions),
                "recognized": format_money(e.recognized),
                "ending": format_money(e.ending),
            }
            for e in entries
        ]
    }
    return output(data, headers=headers, rows=rows, fmt=args.format)
