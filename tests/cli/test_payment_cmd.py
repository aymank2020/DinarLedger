"""Tests for the payment CLI commands."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

import pytest

from dinarledger.cli import store
from dinarledger.cli.main import main
from dinarledger.core.enums import InvoiceStatus
from dinarledger.core.money import Money
from dinarledger.core.types import (
    BillingPeriod,
    Customer,
    Invoice,
    LineItem,
    Plan,
    Subscription,
)
from dinarledger.subscriptions.lifecycle import subscribe


@pytest.fixture(autouse=True)
def _reset_store():
    store.reset()
    yield
    store.reset()


def _seed_invoice():
    """Create a customer, plan, subscription, and invoice."""
    cust_id = store.next_customer_id()
    store.customers[cust_id] = Customer(
        customer_id=cust_id, name="Pay Co", currency="USD",
    )

    plan_id = store.next_plan_id()
    plan = Plan(
        plan_id=plan_id, name="Standard",
        base_price=Money(amount=Decimal("100.00"), currency="USD"),
        billing_cycle="monthly",
    )
    store.plans[plan_id] = plan

    sub = subscribe(cust_id, plan, date(2025, 1, 1))
    store.subscriptions[sub.sub_id] = sub

    inv = Invoice(
        invoice_id="INV-TEST1",
        customer_id=cust_id,
        issue_date=date(2025, 1, 1),
        due_date=date(2025, 1, 31),
        line_items=[
            LineItem(
                description="Subscription",
                amount=Money(amount=Decimal("100.00"), currency="USD"),
            ),
        ],
        status=InvoiceStatus.OPEN,
    )
    store.invoices["INV-TEST1"] = inv
    return inv


class TestPaymentRecord:
    def test_record_payment(self, capsys):
        inv = _seed_invoice()
        result = main([
            "payment", "record",
            "--invoice", inv.invoice_id,
            "--amount", "100.00",
            "--currency", "USD",
        ])
        assert result == 0
        captured = capsys.readouterr()
        assert "100.00 USD" in captured.out

    def test_record_nonexistent_invoice(self):
        result = main([
            "payment", "record",
            "--invoice", "INV-FAKE",
            "--amount", "50.00",
            "--currency", "USD",
        ])
        assert result != 0


class TestPaymentAllocate:
    def test_allocate_oldest_first(self, capsys):
        _seed_invoice()
        result = main([
            "payment", "allocate",
            "--amount", "100.00",
            "--currency", "USD",
            "--strategy", "oldest_first",
        ])
        assert result == 0
        captured = capsys.readouterr()
        assert "INV-TEST" in captured.out

    def test_allocate_no_invoices(self, capsys):
        result = main([
            "payment", "allocate",
            "--amount", "100.00",
            "--currency", "USD",
        ])
        assert result == 0
        captured = capsys.readouterr()
        assert "No outstanding invoices" in captured.out
