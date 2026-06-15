"""Tests for the EntitySerializer and individual adapters.

Covers round-trip serialization/deserialization for Money, Decimal,
date, Enum, and all major domain entity types.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from dinarledger.core.enums import InvoiceStatus, SubscriptionStatus
from dinarledger.core.money import Money
from dinarledger.core.types import (
    BillingPeriod,
    Customer,
    Invoice,
    LineItem,
    Payment,
    PaymentStatus,
    Plan,
    Subscription,
    TaxRate,
)
from dinarledger.fx.rates import FXRate
from dinarledger.storage.serializers import (
    DateAdapter,
    DecimalAdapter,
    EntitySerializer,
    EnumAdapter,
    MoneyAdapter,
    from_json,
    to_json,
)


# ---------------------------------------------------------------------------
# Individual adapters
# ---------------------------------------------------------------------------

class TestMoneyAdapter:
    def test_round_trip(self) -> None:
        money = Money(amount=Decimal("123.45"), currency="KWD")
        serialized = MoneyAdapter.serialize(money)
        assert serialized["_type"] == "Money"
        assert serialized["amount"] == "123.45"
        assert serialized["currency"] == "KWD"

        restored = MoneyAdapter.deserialize(serialized)
        assert restored == money
        assert isinstance(restored.amount, Decimal)

    def test_preserves_precision(self) -> None:
        money = Money(amount=Decimal("0.10"), currency="USD")
        data = MoneyAdapter.serialize(money)
        restored = MoneyAdapter.deserialize(data)
        assert restored.amount == Decimal("0.10")


class TestDecimalAdapter:
    def test_round_trip(self) -> None:
        val = Decimal("3.141592653589793")
        data = DecimalAdapter.serialize(val)
        assert data["_type"] == "Decimal"
        restored = DecimalAdapter.deserialize(data)
        assert restored == val

    def test_negative(self) -> None:
        val = Decimal("-99.99")
        data = DecimalAdapter.serialize(val)
        restored = DecimalAdapter.deserialize(data)
        assert restored == val


class TestDateAdapter:
    def test_round_trip(self) -> None:
        d = date(2025, 3, 15)
        data = DateAdapter.serialize(d)
        assert data["_type"] == "Date"
        assert data["value"] == "2025-03-15"
        restored = DateAdapter.deserialize(data)
        assert restored == d


class TestEnumAdapter:
    def test_round_trip(self) -> None:
        status = InvoiceStatus.PAID
        data = EnumAdapter.serialize(status)
        assert data["_type"] == "Enum"
        assert data["enum_class"] == "InvoiceStatus"
        assert data["value"] == "paid"
        restored = EnumAdapter.deserialize(data)
        assert restored == InvoiceStatus.PAID

    def test_subscription_status(self) -> None:
        status = SubscriptionStatus.ACTIVE
        data = EnumAdapter.serialize(status)
        restored = EnumAdapter.deserialize(data)
        assert restored == SubscriptionStatus.ACTIVE


# ---------------------------------------------------------------------------
# EntitySerializer
# ---------------------------------------------------------------------------

class TestEntitySerializer:
    def test_customer_round_trip(self) -> None:
        cust = Customer(customer_id="c1", name="Acme", currency="KWD")
        data = EntitySerializer.serialize(cust)
        assert data["_type"] == "Customer"
        restored = EntitySerializer.deserialize(data)
        assert restored.customer_id == "c1"
        assert restored.name == "Acme"
        assert restored.currency == "KWD"

    def test_plan_with_money(self) -> None:
        plan = Plan(
            plan_id="p1",
            name="Pro",
            base_price=Money(amount=Decimal("49.99"), currency="USD"),
            billing_cycle="monthly",
        )
        data = EntitySerializer.serialize(plan)
        restored = EntitySerializer.deserialize(data)
        assert restored.plan_id == "p1"
        assert restored.base_price.amount == Decimal("49.99")
        assert restored.base_price.currency == "USD"

    def test_billing_period(self) -> None:
        bp = BillingPeriod(start_date=date(2025, 1, 1), end_date=date(2025, 1, 31))
        data = EntitySerializer.serialize(bp)
        restored = EntitySerializer.deserialize(data)
        assert restored.start_date == date(2025, 1, 1)
        assert restored.end_date == date(2025, 1, 31)

    def test_tax_rate(self) -> None:
        tr = TaxRate(code="VAT", rate=Decimal("0.05"), description="5% VAT")
        data = EntitySerializer.serialize(tr)
        restored = EntitySerializer.deserialize(data)
        assert restored.code == "VAT"
        assert restored.rate == Decimal("0.05")

    def test_fx_rate(self) -> None:
        fx = FXRate(base="USD", quote="KWD", rate=Decimal("0.31"), rate_date=date(2025, 6, 1))
        data = EntitySerializer.serialize(fx)
        restored = EntitySerializer.deserialize(data)
        assert restored.base == "USD"
        assert restored.rate == Decimal("0.31")

    def test_none_handling(self) -> None:
        assert EntitySerializer.serialize(None) is None
        assert EntitySerializer.deserialize(None) is None


# ---------------------------------------------------------------------------
# JSON convenience helpers
# ---------------------------------------------------------------------------

class TestJsonHelpers:
    def test_to_json_and_back(self) -> None:
        cust = Customer(customer_id="c1", name="Test", currency="USD")
        text = to_json(cust)
        assert isinstance(text, str)
        restored = from_json(text)
        assert restored.customer_id == cust.customer_id
        assert restored.name == cust.name

    def test_to_json_with_indent(self) -> None:
        cust = Customer(customer_id="c1", name="Test", currency="USD")
        text = to_json(cust, indent=2)
        assert "\n" in text
