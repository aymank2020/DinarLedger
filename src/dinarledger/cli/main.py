"""Top-level argparse definition and subcommand router.

Usage::

    python -m dinarledger <command> <subcommand> [options]

Supported commands: customer, plan, subscription, invoice, payment,
revenue, fx, report.
"""

from __future__ import annotations

import argparse
import sys

from dinarledger.cli.formatters import resolve_format


def build_parser() -> argparse.ArgumentParser:
    """Construct and return the top-level argument parser."""
    parser = argparse.ArgumentParser(
        prog="dinarledger",
        description="DinarLedger — multi-currency subscription billing CLI",
    )
    parser.add_argument(
        "--format",
        choices=["table", "json", "csv"],
        default=None,
        help="Output format (default: table, or OUTPUT_FORMAT env var)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Defer imports to avoid circular dependencies
    from dinarledger.cli.commands import customer, plan, subscription
    from dinarledger.cli.commands import invoice, payment, revenue, fx, report

    customer.register(subparsers)
    plan.register(subparsers)
    subscription.register(subparsers)
    invoice.register(subparsers)
    payment.register(subparsers)
    revenue.register(subparsers)
    fx.register(subparsers)
    report.register(subparsers)

    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point for the CLI.

    Returns an exit code (0 for success, non-zero for errors).
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    # Attach resolved format to args for subcommands to use
    args.format = resolve_format(args.format)

    # Dispatch to the subcommand handler
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 1

    try:
        result = handler(args)
        if result is not None:
            print(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
