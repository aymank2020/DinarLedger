"""Tests for the SQLite-backed repository.

Covers CRUD operations, transaction semantics, schema auto-creation,
and filtering.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from dinarledger.core.enums import InvoiceStatus, SubscriptionStatus
from dinarledger.core.money import Money
from dinarledger.core.types import Customer, Plan
from dinarledger.storage.base import EntityNotFoundError, FilterCondition, FilterOperator
from dinarledger.storage.sqlite_store import SqliteRepository


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def customer_db(tmp_path: Path) -> SqliteRepository[Customer]:
    db_path = tmp_path / "test.db"
    return SqliteRepository(Customer, db_path)


@pytest.fixture
def plan_db(tmp_path: Path) -> SqliteRepository[Plan]:
    db_path = tmp_path / "test.db"
    return SqliteRepository(Plan, db_path)


# ---------------------------------------------------------------------------
# Schema creation
# ---------------------------------------------------------------------------

class TestSqliteSchema:
    def test_auto_creates_table(self, customer_db: SqliteRepository[Customer]) -> None:
        """The table should be created automatically on init."""
        # If we can add without error, the table exists
        cust = Customer(customer_id="c1", name="Acme", currency="USD")
        customer_db.add(cust)
        assert customer_db.count() == 1

    def test_table_name_defaults_to_class(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        repo = SqliteRepository(Customer, db_path)
        assert repo._table_name == "customer"


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

class TestSqliteCRUD:
    def test_add_and_get(self, customer_db: SqliteRepository[Customer]) -> None:
        cust = Customer(customer_id="c1", name="Acme", currency="USD")
        customer_db.add(cust)
        result = customer_db.get("c1")
        assert result is not None
        assert result.name == "Acme"
        assert result.currency == "USD"

    def test_get_returns_none_for_missing(self, customer_db: SqliteRepository[Customer]) -> None:
        assert customer_db.get("nonexistent") is None

    def test_get_all(self, customer_db: SqliteRepository[Customer]) -> None:
        customer_db.add(Customer(customer_id="c1", name="A", currency="USD"))
        customer_db.add(Customer(customer_id="c2", name="B", currency="KWD"))
        all_items = customer_db.get_all()
        assert len(all_items) == 2

    def test_update(self, customer_db: SqliteRepository[Customer]) -> None:
        customer_db.add(Customer(customer_id="c1", name="Old", currency="USD"))
        customer_db.update(Customer(customer_id="c1", name="New", currency="USD"))
        result = customer_db.get("c1")
        assert result is not None
        assert result.name == "New"

    def test_update_missing_raises(self, customer_db: SqliteRepository[Customer]) -> None:
        with pytest.raises(EntityNotFoundError):
            customer_db.update(Customer(customer_id="missing", name="X", currency="USD"))

    def test_delete(self, customer_db: SqliteRepository[Customer]) -> None:
        customer_db.add(Customer(customer_id="c1", name="A", currency="USD"))
        assert customer_db.delete("c1") is True
        assert customer_db.get("c1") is None
        assert customer_db.delete("c1") is False

    def test_add_and_get_plan_with_money(self, plan_db: SqliteRepository[Plan]) -> None:
        plan = Plan(
            plan_id="p1",
            name="Pro",
            base_price=Money(amount=Decimal("99.99"), currency="USD"),
            billing_cycle="monthly",
        )
        plan_db.add(plan)
        result = plan_db.get("p1")
        assert result is not None
        assert result.name == "Pro"
        assert result.base_price.amount == Decimal("99.99")
        assert result.base_price.currency == "USD"


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------

class TestSqliteFind:
    def test_find_by_field(self, customer_db: SqliteRepository[Customer]) -> None:
        customer_db.add(Customer(customer_id="c1", name="A", currency="USD"))
        customer_db.add(Customer(customer_id="c2", name="B", currency="KWD"))
        result = customer_db.find({"currency": "KWD"})
        assert len(result) == 1
        assert result[0].customer_id == "c2"

    def test_find_with_conditions(self, customer_db: SqliteRepository[Customer]) -> None:
        customer_db.add(Customer(customer_id="c1", name="A", currency="USD", tax_exempt=False))
        customer_db.add(Customer(customer_id="c2", name="B", currency="KWD", tax_exempt=True))
        conds = [FilterCondition(field="tax_exempt", operator=FilterOperator.EQ, value=True)]
        result = customer_db.find_with_conditions(conds)
        assert len(result) == 1
        assert result[0].customer_id == "c2"


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------

class TestSqliteTransactions:
    def test_transaction_commit(self, customer_db: SqliteRepository[Customer]) -> None:
        with customer_db.transaction():
            customer_db.add(Customer(customer_id="c1", name="A", currency="USD"))
        assert customer_db.get("c1") is not None

    def test_transaction_rollback(self, customer_db: SqliteRepository[Customer]) -> None:
        try:
            with customer_db.transaction():
                customer_db.add(Customer(customer_id="c1", name="A", currency="USD"))
                raise RuntimeError("boom")
        except RuntimeError:
            pass
        assert customer_db.get("c1") is None

    def test_count(self, customer_db: SqliteRepository[Customer]) -> None:
        assert customer_db.count() == 0
        customer_db.add(Customer(customer_id="c1", name="A", currency="USD"))
        assert customer_db.count() == 1
