"""Tests for the customer CLI commands."""

from __future__ import annotations

import json

import pytest

from dinarledger.cli import store
from dinarledger.cli.main import main


@pytest.fixture(autouse=True)
def _reset_store():
    """Reset the in-memory store before each test."""
    store.reset()
    yield
    store.reset()


class TestCustomerCreate:
    def test_create_customer(self, capsys):
        result = main([
            "customer", "create",
            "--name", "Acme Corp",
            "--currency", "KWD",
        ])
        assert result == 0
        captured = capsys.readouterr()
        assert "Acme Corp" in captured.out
        assert "KWD" in captured.out

    def test_create_with_credit_limit(self, capsys):
        result = main([
            "customer", "create",
            "--name", "Big Corp",
            "--currency", "USD",
            "--credit-limit", "50000",
        ])
        assert result == 0
        captured = capsys.readouterr()
        assert "50,000.00 USD" in captured.out

    def test_create_json_output(self, capsys):
        result = main([
            "--format", "json",
            "customer", "create",
            "--name", "JSON Corp",
            "--currency", "EUR",
        ])
        assert result == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["name"] == "JSON Corp"
        assert data["currency"] == "EUR"


class TestCustomerList:
    def test_list_empty(self, capsys):
        result = main(["customer", "list"])
        assert result == 0
        captured = capsys.readouterr()
        assert "No customers" in captured.out

    def test_list_after_create(self, capsys):
        main(["customer", "create", "--name", "Alpha", "--currency", "USD"])
        capsys.readouterr()  # clear
        result = main(["customer", "list"])
        assert result == 0
        captured = capsys.readouterr()
        assert "Alpha" in captured.out


class TestCustomerShow:
    def test_show_existing(self, capsys):
        main(["customer", "create", "--name", "Beta", "--currency", "KWD"])
        capsys.readouterr()
        cust_id = list(store.customers.keys())[0]
        result = main(["customer", "show", cust_id])
        assert result == 0
        captured = capsys.readouterr()
        assert "Beta" in captured.out

    def test_show_nonexistent(self):
        result = main(["customer", "show", "C-9999"])
        assert result != 0
