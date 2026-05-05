"""Tests for dinarledger.core.money — Money value object."""

from __future__ import annotations

from decimal import Decimal

import pytest

from dinarledger.core.errors import CurrencyMismatchError
from dinarledger.core.money import Money, sum_money, zero


class TestMoneyAddition:
    """Money.__add__ tests."""

    def test_addition_same_currency(self) -> None:
        a = Money(Decimal("10.25"), "USD")
        b = Money(Decimal("5.75"), "USD")
        result = a + b
        assert result == Money(Decimal("16.00"), "USD")

    def test_addition_different_currency_raises(self) -> None:
        a = Money(Decimal("10"), "USD")
        b = Money(Decimal("10"), "EGP")
        with pytest.raises(CurrencyMismatchError):
            a + b


class TestMoneySubtraction:
    """Money.__sub__ tests."""

    def test_subtraction(self) -> None:
        a = Money(Decimal("20.00"), "USD")
        b = Money(Decimal("7.50"), "USD")
        result = a - b
        assert result == Money(Decimal("12.50"), "USD")


class TestMoneyMultiplication:
    """Money.__mul__ tests."""

    def test_multiplication_by_scalar(self) -> None:
        m = Money(Decimal("33.33"), "USD")
        result = m * 3
        assert result == Money(Decimal("99.99"), "USD")

    def test_multiplication_by_float(self) -> None:
        m = Money(Decimal("100"), "USD")
        result = m * 0.5
        assert result == Money(Decimal("50.00"), "USD")

    def test_rmul(self) -> None:
        m = Money(Decimal("50"), "USD")
        result = 2 * m
        assert result == Money(Decimal("100.00"), "USD")


class TestMoneyQuantize:
    """Quantisation via quantize() method."""

    def test_quantize(self) -> None:
        m = Money(Decimal("9.9999"), "USD")
        result = m.quantize()
        assert result.amount == Decimal("10.00")

    def test_quantize_truncation(self) -> None:
        m = Money(Decimal("1.114"), "USD")
        result = m.quantize()
        # ROUND_HALF_EVEN → 1.11 (rounds to even last digit)
        assert result.amount == Decimal("1.11")


class TestMoneyAllocate:
    """Money.allocate tests."""

    def test_allocate_equal_split(self) -> None:
        """$100 split 1:1:1 → 33.34, 33.33, 33.33."""
        result = Money(Decimal("100.00"), "USD").allocate(
            [Decimal("1"), Decimal("1"), Decimal("1")]
        )
        assert len(result) == 3
        # Sum must equal original (quantised)
        total = sum_money(result)
        assert total == Money(Decimal("100.00"), "USD")
        # First gets the rounding penny (last bucket absorbs remainder)
        assert result[-1].amount == Decimal("33.34")

    def test_allocate_unequal_split(self) -> None:
        """$100 split 3:2:1."""
        result = Money(Decimal("100.00"), "USD").allocate(
            [Decimal("3"), Decimal("2"), Decimal("1")]
        )
        total = sum_money(result)
        assert total == Money(Decimal("100.00"), "USD")
        # 3/6 = 50.00, 2/6 = 33.33, 1/6 = 16.67
        assert result[0].amount == Decimal("50.00")
        assert result[1].amount == Decimal("33.33")
        assert result[2].amount == Decimal("16.67")

    def test_allocate_penny_rounding(self) -> None:
        """3-way split of $0.01 must still sum to $0.01."""
        result = Money(Decimal("0.01"), "USD").allocate(
            [Decimal("1"), Decimal("1"), Decimal("1")]
        )
        total = sum_money(result)
        assert total == Money(Decimal("0.01"), "USD")
        # Last bucket absorbs remainder, so it gets the penny
        penny_holders = [r for r in result if r.amount > Decimal("0")]
        assert len(penny_holders) == 1


class TestMoneySum:
    """sum_money tests."""

    def test_sum_money(self) -> None:
        items = [
            Money(Decimal("10.00"), "USD"),
            Money(Decimal("20.00"), "USD"),
            Money(Decimal("30.00"), "USD"),
        ]
        result = sum_money(items)
        assert result == Money(Decimal("60.00"), "USD")

    def test_sum_money_empty(self) -> None:
        result = sum_money([], "USD")
        assert result == zero("USD")


class TestMoneyZero:
    """Money.zero classmethod and module-level zero() tests."""

    def test_zero_classmethod(self) -> None:
        z = Money.zero("USD")
        assert z.amount == Decimal("0")
        assert z.currency == "USD"
        assert z.is_zero()

    def test_zero_function(self) -> None:
        z = zero("EGP")
        assert z.amount == Decimal("0")
        assert z.currency == "EGP"
        assert z.is_zero()


class TestMoneyFromFloat:
    """Money.from_float tests."""

    def test_from_float(self) -> None:
        m = Money.from_float(19.99, "USD")
        assert m.amount == Decimal("19.99")
        assert m.currency == "USD"

    def test_from_float_rounding(self) -> None:
        # Float that can't be represented exactly — from_float preserves
        # the string representation of the float, which may include
        # float-point artefacts.  Use quantize() for a clean result.
        m = Money.from_float(0.1 + 0.2, "USD")
        clean = m.quantize()
        assert clean.amount == Decimal("0.30")
