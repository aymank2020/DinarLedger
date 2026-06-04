"""In-memory session store for CLI commands.

Persistence is not yet available (Phase C), so all data lives in
module-level dictionaries for the duration of the CLI process.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Dict, List

from dinarledger.core.money import Money
from dinarledger.core.types import (
    Customer,
    Invoice,
    Payment,
    Plan,
    Subscription,
    TaxRate,
)
from dinarledger.fx.rates import FXRate

# ── In-memory collections ──────────────────────────────────────────────────

customers: Dict[str, Customer] = {}
plans: Dict[str, Plan] = {}
subscriptions: Dict[str, Subscription] = {}
invoices: Dict[str, Invoice] = {}
payments: Dict[str, Payment] = {}
tax_rates: Dict[str, TaxRate] = {}
fx_rates: List[FXRate] = []

# ── Auto-ID counters ──────────────────────────────────────────────────────

_customer_counter = 0
_plan_counter = 0
_payment_counter = 0


def next_customer_id() -> str:
    global _customer_counter
    _customer_counter += 1
    return f"C-{_customer_counter:04d}"


def next_plan_id() -> str:
    global _plan_counter
    _plan_counter += 1
    return f"PLAN-{_plan_counter:04d}"


def next_payment_id() -> str:
    global _payment_counter
    _payment_counter += 1
    return f"PAY-{_payment_counter:04d}"


def reset() -> None:
    """Clear all stores — useful for testing."""
    global _customer_counter, _plan_counter, _payment_counter
    customers.clear()
    plans.clear()
    subscriptions.clear()
    invoices.clear()
    payments.clear()
    tax_rates.clear()
    fx_rates.clear()
    _customer_counter = 0
    _plan_counter = 0
    _payment_counter = 0
