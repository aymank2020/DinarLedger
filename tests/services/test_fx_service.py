"""Tests for FXService — rate updates, conversion, revaluation."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from dinarledger.core.errors import RateNotFoundError
from dinarledger.core.money import Money
from dinarledger.core.types import Invoice, LineItem
from dinarledger.fx.rates import FXRate
from dinarledger.services.fx_service import FXService


@pytest.fixture
def svc() -> FXService:
    return FXService()


@pytest.fixture
def usd_eur_rate() -> FXRate:
    return FXRate(
        base="USD", quote="EUR", rate=Decimal("0.92"), rate_date=date(2025, 3, 15)
    )


@pytest.fixture
def eur_usd_rate() -> FXRate:
    return FXRate(
        base="EUR", quote="USD", rate=Decimal("1.0870"), rate_date=date(2025, 3, 15)
    )


# ── Rate management ─────────────────────────────────────────────────────────

class TestUpdateRates:
    def test_bulk_update(self, svc: FXService, usd_eur_rate: FXRate) -> None:
        svc.update_rates({"USD/EUR": usd_eur_rate})
        assert svc.get_rate("USD", "EUR") is not None

    def test_get_nonexistent_rate(self, svc: FXService) -> None:
        assert svc.get_rate("XYZ", "ABC") is None

    def test_overwrite_rate(self, svc: FXService) -> None:
        old = FXRate(base="USD", quote="EUR", rate=Decimal("0.90"), rate_date=date(2025, 1, 1))
        new = FXRate(base="USD", quote="EUR", rate=Decimal("0.92"), rate_date=date(2025, 3, 15))
        svc.update_rates({"USD/EUR": old})
        svc.update_rates({"USD/EUR": new})
        assert svc.get_rate("USD", "EUR").rate == Decimal("0.92")


# ── Conversion ──────────────────────────────────────────────────────────────

class TestConvertAmount:
    def test_direct_conversion(self, svc: FXService, usd_eur_rate: FXRate) -> None:
        svc.update_rates({"USD/EUR": usd_eur_rate})
        result = svc.convert_amount(Money(Decimal("100"), "USD"), "EUR")
        assert result.currency == "EUR"
        assert result.amount == Decimal("92.00")

    def test_inverse_conversion(self, svc: FXService, usd_eur_rate: FXRate) -> None:
        svc.update_rates({"USD/EUR": usd_eur_rate})
        result = svc.convert_amount(Money(Decimal("100"), "EUR"), "USD")
        assert result.currency == "USD"
        # 100 EUR * (1 / 0.92) ≈ 108.70
        assert result.amount > Decimal("100")

    def test_same_currency_returns_same(self, svc: FXService) -> None:
        money = Money(Decimal("100"), "USD")
        result = svc.convert_amount(money, "USD")
        assert result == money

    def test_missing_rate_raises(self, svc: FXService) -> None:
        with pytest.raises(RateNotFoundError):
            svc.convert_amount(Money(Decimal("100"), "GBP"), "JPY")

    def test_cross_rate_via_usd(self, svc: FXService) -> None:
        svc.update_rates({
            "USD/EUR": FXRate(base="USD", quote="EUR", rate=Decimal("0.92"), rate_date=date(2025, 3, 15)),
            "USD/GBP": FXRate(base="USD", quote="GBP", rate=Decimal("0.79"), rate_date=date(2025, 3, 15)),
        })
        result = svc.convert_amount(Money(Decimal("100"), "EUR"), "GBP")
        assert result.currency == "GBP"
        assert result.amount > Decimal("0")

    def test_custom_rates_dict(self, svc: FXService) -> None:
        """Passing rates directly overrides the service's store."""
        custom = {
            "USD/EUR": FXRate(base="USD", quote="EUR", rate=Decimal("0.85"), rate_date=date(2025, 1, 1)),
        }
        result = svc.convert_amount(Money(Decimal("100"), "USD"), "EUR", rates=custom)
        assert result.amount == Decimal("85.00")


# ── Revaluation ─────────────────────────────────────────────────────────────

class TestScheduleRevaluation:
    def test_revalue_foreign_currency_invoices(self, svc: FXService) -> None:
        inv = Invoice(
            invoice_id="inv-eur",
            customer_id="c1",
            issue_date=date(2025, 1, 1),
            due_date=date(2025, 1, 31),
            line_items=[LineItem(description="Charge", amount=Money(Decimal("1000"), "EUR"))],
        )
        rates = {"EUR": Decimal("1.10")}
        results = svc.schedule_revaluation([inv], rates, base_currency="USD")
        assert len(results) == 1
        assert results[0][0] == "inv-eur"
        # Gain/loss should be a Money instance
        assert isinstance(results[0][1], Money)

    def test_skip_base_currency_invoices(self, svc: FXService) -> None:
        inv = Invoice(
            invoice_id="inv-usd",
            customer_id="c1",
            issue_date=date(2025, 1, 1),
            due_date=date(2025, 1, 31),
            line_items=[LineItem(description="Charge", amount=Money(Decimal("500"), "USD"))],
        )
        results = svc.schedule_revaluation([inv], {"EUR": Decimal("1.10")}, base_currency="USD")
        assert len(results) == 0

    def test_empty_invoices(self, svc: FXService) -> None:
        results = svc.schedule_revaluation([], {"EUR": Decimal("1.10")})
        assert results == []
