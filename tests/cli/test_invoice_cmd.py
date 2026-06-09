"""Tests for the invoice CLI commands."""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from dinarledger.cli import store
from dinarledger.cli.main import main
from dinarledger.core.enums import SubscriptionStatus
from dinarledger.core.money import Money
from dinarledger.core.types import Plan, Subscription


@pytest.fixture(autouse=True)
def _reset_store():
    store.reset()
    yield
    store.reset()


def _seed_subscription():
    """Create a customer, plan, and active subscription in the store."""
    from dinarledger.subscriptions.lifecycle import subscribe

    cust_id = store.next_customer_id()
    from dinarledger.core.types import Customer
    store.customers[cust_id] = Customer(
        customer_id=cust_id, name="Test Co", currency="USD",
    )

    plan_id = store.next_plan_id()
    plan = Plan(
        plan_id=plan_id, name="Basic",
        base_price=Money(amount=Decimal("100.00"), currency="USD"),
        billing_cycle="monthly",
    )
    store.plans[plan_id] = plan

    from datetime import date
    sub = subscribe(cust_id, plan, date(2025, 1, 1))
    store.subscriptions[sub.sub_id] = sub
    return sub


class TestInvoiceGenerate:
    def test_generate_invoice(self, capsys):
        sub = _seed_subscription()
        result = main([
            "invoice", "generate",
            "--sub", sub.sub_id,
            "--start", "2025-01-01",
            "--end", "2025-01-31",
        ])
        assert result == 0
        captured = capsys.readouterr()
        assert "invoice_id" in captured.out or "Invoice" in captured.out

    def test_generate_first_invoice(self, capsys):
        sub = _seed_subscription()
        result = main([
            "invoice", "generate",
            "--sub", sub.sub_id,
            "--start", "2025-01-01",
            "--end", "2025-01-31",
            "--first",
        ])
        assert result == 0

    def test_generate_json_output(self, capsys):
        sub = _seed_subscription()
        result = main([
            "--format", "json",
            "invoice", "generate",
            "--sub", sub.sub_id,
            "--start", "2025-01-01",
            "--end", "2025-01-31",
        ])
        assert result == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "invoice_id" in data


class TestInvoiceVoid:
    def test_void_invoice(self, capsys):
        sub = _seed_subscription()
        main([
            "invoice", "generate",
            "--sub", sub.sub_id,
            "--start", "2025-01-01",
            "--end", "2025-01-31",
        ])
        capsys.readouterr()
        inv_id = list(store.invoices.keys())[0]
        result = main(["invoice", "void", inv_id])
        assert result == 0
        captured = capsys.readouterr()
        assert "voided" in captured.out.lower()

    def test_void_nonexistent(self):
        result = main(["invoice", "void", "nonexistent-id"])
        assert result != 0


class TestInvoiceList:
    def test_list_empty(self, capsys):
        result = main(["invoice", "list"])
        assert result == 0
        captured = capsys.readouterr()
        assert "No invoices" in captured.out
