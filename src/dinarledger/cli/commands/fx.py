"""``fx`` subcommand — rates and currency conversion.

Examples::

    dinarledger fx rates
    dinarledger fx convert --amount 100.00 --from USD --to KWD --rate 0.307
"""

from __future__ import annotations

import argparse
from decimal import Decimal

from dinarledger.cli import store
from dinarledger.cli.formatters import format_money, output
from dinarledger.core.money import Money
from dinarledger.fx.rates import FXRate, convert, cross_rate


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``fx`` subcommand group."""
    parser = subparsers.add_parser("fx", help="FX rates and conversion")
    sub = parser.add_subparsers(dest="fx_action")

    # rates
    rates_p = sub.add_parser("rates", help="List stored FX rates")
    rates_p.set_defaults(handler=_cmd_rates)

    # convert
    conv_p = sub.add_parser("convert", help="Convert an amount between currencies")
    conv_p.add_argument("--amount", required=True, type=float, help="Amount to convert")
    conv_p.add_argument("--from", dest="from_currency", required=True,
                        help="Source currency")
    conv_p.add_argument("--to", dest="to_currency", required=True,
                        help="Target currency")
    conv_p.add_argument("--rate", required=True, type=float,
                        help="Exchange rate (1 source = rate target)")
    conv_p.set_defaults(handler=_cmd_convert)


# ── Command implementations ──────────────────────────────────────────────

def _cmd_rates(args: argparse.Namespace) -> str:
    if not store.fx_rates:
        return "No FX rates stored."

    headers = ["Base", "Quote", "Rate", "Date"]
    rows = [
        [r.base, r.quote, str(r.rate), str(r.rate_date)]
        for r in store.fx_rates
    ]
    data = [
        {"base": r.base, "quote": r.quote, "rate": str(r.rate), "date": str(r.rate_date)}
        for r in store.fx_rates
    ]
    return output(data, headers=headers, rows=rows, fmt=args.format)


def _cmd_convert(args: argparse.Namespace) -> str:
    source = Money(
        amount=Decimal(str(args.amount)),
        currency=args.from_currency,
    )
    rate = Decimal(str(args.rate))
    result = convert(source, args.to_currency, rate)

    data = {
        "source": format_money(source),
        "target": format_money(result),
        "rate": str(rate),
    }
    return output(data, fmt=args.format)
