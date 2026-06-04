"""DinarLedger CLI — command-line interface for subscription billing.

Provides an argparse-based CLI with subcommands for customers, plans,
subscriptions, invoices, payments, revenue recognition, FX, and reports.

Usage::

    python -m dinarledger <command> <subcommand> [options]
    dinarledger <command> <subcommand> [options]
"""

from dinarledger.cli.main import main

__all__ = ["main"]
