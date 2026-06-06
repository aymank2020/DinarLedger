"""CLI subcommand registry.

Each command module exposes a ``register(subparsers)`` function that
registers its subcommand(s) with the top-level argparse subparsers
action.
"""

from dinarledger.cli.commands import (
    customer,
    fx,
    invoice,
    payment,
    plan,
    report,
    revenue,
    subscription,
)

__all__ = [
    "customer",
    "fx",
    "invoice",
    "payment",
    "plan",
    "report",
    "revenue",
    "subscription",
]
