"""Property-based tests for Money arithmetic and allocation.

Uses Hypothesis to verify algebraic properties (associativity,
commutativity, identity, etc.) and allocation invariants of the
dinarledger.core.money module across a wide range of Decimal amounts
and currency codes.
"""

from decimal import Decimal

import pytest
from hypothesis import given, assume, settings
from hypothesis.strategies import (
    builds,
    decimals,
    text,
    lists,
    shared,
    sampled_from,
    integers,
    just,
    composite,
)

from dinarledger.core.money import Money, sum_money
from dinarledger.core.errors import CurrencyMismatchError


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Finite-precision Decimal amounts (avoid NaN / Infinity / excessive scale).
_amount_strategy = decimals(
    min_value=Decimal("-9999999"),
    max_value=Decimal("9999999"),
    places=6,
    allow_nan=False,
    allow_infinity=False,
)

# A small set of realistic currency codes keeps the example space tractable.
_currency_strategy = sampled_from(["USD", "EUR", "KWD", "GBP", "JPY", "SAR"])

# Build a Money object with a random amount and currency.
money_strategy = builds(Money, amount=_amount_strategy, currency=_currency_strategy)


def _same_currency_money(currency: str):
    """Strategy for Money values in a single fixed *currency*."""
    return builds(Money, amount=_amount_strategy, currency=just(currency))


@composite
def ordered_same_currency_triple(draw):
    """Generate three same-currency Money values with a.amount < b.amount < c.amount."""
    currency = draw(_currency_strategy)
    a_val = draw(decimals(
        min_value=Decimal("-9999"), max_value=Decimal("9999"),
        places=2, allow_nan=False, allow_infinity=False,
    ))
    gap1 = draw(decimals(
        min_value=Decimal("0.01"), max_value=Decimal("1000"),
        places=2, allow_nan=False, allow_infinity=False,
    ))
    gap2 = draw(decimals(
        min_value=Decimal("0.01"), max_value=Decimal("1000"),
        places=2, allow_nan=False, allow_infinity=False,
    ))
    b_val = a_val + gap1
    c_val = b_val + gap2
    return (
        Money(amount=a_val, currency=currency),
        Money(amount=b_val, currency=currency),
        Money(amount=c_val, currency=currency),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestMoneyArithmeticProperties:
    """Algebraic properties of Money addition, subtraction, and scaling."""

    @given(currency=_currency_strategy, a=_amount_strategy, b=_amount_strategy, c=_amount_strategy)
    @settings(max_examples=80)
    def test_addition_associative_same_currency(self, currency, a, b, c):
        """(a + b) + c == a + (b + c) when all share the same currency."""
        ma = Money(amount=a, currency=currency)
        mb = Money(amount=b, currency=currency)
        mc = Money(amount=c, currency=currency)
        lhs = (ma + mb) + mc
        rhs = ma + (mb + mc)
        assert lhs == rhs

    @given(currency=_currency_strategy, a=_amount_strategy, b=_amount_strategy)
    @settings(max_examples=80)
    def test_addition_commutative_same_currency(self, currency, a, b):
        """a + b == b + a when both share the same currency."""
        ma = Money(amount=a, currency=currency)
        mb = Money(amount=b, currency=currency)
        assert ma + mb == mb + ma

    @given(m=money_strategy)
    def test_subtraction_with_self_gives_zero(self, m):
        """m - m yields a zero-amount Money in the same currency."""
        result = m - m
        assert result.is_zero()
        assert result.currency == m.currency

    @given(m=money_strategy)
    def test_multiplication_by_one_is_identity(self, m):
        """m * 1 == m for integer factor 1."""
        assert m * 1 == m

    @given(m=money_strategy)
    def test_multiplication_by_decimal_one_is_identity(self, m):
        """m * Decimal('1') == m for Decimal factor."""
        assert m * Decimal("1") == m

    @given(m=money_strategy)
    def test_multiplication_by_zero_gives_zero_amount(self, m):
        """m * 0 yields a zero-amount Money (same currency)."""
        result = m * 0
        assert result.is_zero()
        assert result.currency == m.currency

    @given(m=money_strategy)
    def test_left_multiplication_by_zero(self, m):
        """0 * m also yields a zero-amount Money."""
        result = 0 * m
        assert result.is_zero()
        assert result.currency == m.currency


class TestMoneyQuantizeProperties:
    """Properties of the quantize rounding method."""

    @given(m=money_strategy)
    def test_quantize_preserves_currency(self, m):
        """quantize() always keeps the same currency code."""
        q = m.quantize()
        assert q.currency == m.currency

    @given(m=money_strategy)
    def test_quantize_default_two_decimals(self, m):
        """Default quantize() rounds to two decimal places."""
        q = m.quantize()
        # The quantised amount, when rendered, has at most 2 decimal places.
        assert q.amount == q.amount.quantize(Decimal("0.01"))

    @given(m=money_strategy)
    def test_quantize_custom_exp(self, m):
        """quantize() with a custom exponent still preserves currency."""
        exp = Decimal("0.0001")
        q = m.quantize(exp)
        assert q.currency == m.currency
        assert q.amount == q.amount.quantize(exp)


class TestMoneyAllocateProperties:
    """Properties of the allocate (split) method."""

    @given(
        amount=_amount_strategy.filter(lambda x: x > Decimal("0")),
        currency=_currency_strategy,
        ratios=lists(
            decimals(
                min_value=Decimal("1"),
                max_value=Decimal("1000"),
                places=2,
                allow_nan=False,
                allow_infinity=False,
            ),
            min_size=2,
            max_size=8,
        ),
    )
    @settings(max_examples=60)
    def test_allocate_sums_back_to_original(self, amount, currency, ratios):
        """The sum of allocated parts equals the quantised original amount."""
        m = Money(amount=amount, currency=currency)
        parts = m.allocate(ratios)
        total = sum_money(parts)
        assert total == m.quantize()

    @given(
        amount=_amount_strategy.filter(lambda x: x > Decimal("0")),
        currency=_currency_strategy,
        ratios=lists(
            decimals(
                min_value=Decimal("1"),
                max_value=Decimal("100"),
                places=0,
                allow_nan=False,
                allow_infinity=False,
            ),
            min_size=2,
            max_size=5,
        ),
    )
    @settings(max_examples=50)
    def test_allocate_preserves_currency(self, amount, currency, ratios):
        """Every allocated share has the same currency as the source Money."""
        m = Money(amount=amount, currency=currency)
        parts = m.allocate(ratios)
        for part in parts:
            assert part.currency == currency

    @given(
        amount=_amount_strategy.filter(lambda x: x > Decimal("0")),
        currency=_currency_strategy,
        ratios=lists(
            decimals(
                min_value=Decimal("1"),
                max_value=Decimal("1000"),
                places=2,
                allow_nan=False,
                allow_infinity=False,
            ),
            min_size=2,
            max_size=6,
        ),
    )
    @settings(max_examples=50)
    def test_allocate_result_count_matches_ratios(self, amount, currency, ratios):
        """allocate() returns exactly len(ratios) Money objects."""
        m = Money(amount=amount, currency=currency)
        parts = m.allocate(ratios)
        assert len(parts) == len(ratios)


class TestMoneyCurrencyMismatch:
    """CurrencyMismatchError is raised on cross-currency operations."""

    @given(a=money_strategy, b=money_strategy)
    def test_addition_raises_on_different_currencies(self, a, b):
        """Adding Money in different currencies raises CurrencyMismatchError."""
        assume(a.currency != b.currency)
        with pytest.raises(CurrencyMismatchError):
            _ = a + b

    @given(a=money_strategy, b=money_strategy)
    def test_subtraction_raises_on_different_currencies(self, a, b):
        """Subtracting Money in different currencies raises CurrencyMismatchError."""
        assume(a.currency != b.currency)
        with pytest.raises(CurrencyMismatchError):
            _ = a - b

    @given(a=money_strategy, b=money_strategy)
    def test_comparison_lt_raises_on_different_currencies(self, a, b):
        """Comparing Money in different currencies with < raises CurrencyMismatchError."""
        assume(a.currency != b.currency)
        with pytest.raises(CurrencyMismatchError):
            _ = a < b


class TestMoneyComparisonTransitivity:
    """Comparison operators are transitive for same-currency Money."""

    @given(triple=ordered_same_currency_triple())
    @settings(max_examples=80)
    def test_lt_transitive_same_currency(self, triple):
        """If a < b and b < c then a < c (same currency)."""
        a, b, c = triple
        assert a < b
        assert b < c
        assert a < c

    @given(triple=ordered_same_currency_triple())
    @settings(max_examples=80)
    def test_le_transitive_same_currency(self, triple):
        """If a <= b and b <= c then a <= c (same currency)."""
        a, b, c = triple
        assert a <= b
        assert b <= c
        assert a <= c


class TestSumMoneyProperty:
    """sum_money of a list equals sequential addition."""

    @given(
        currency=_currency_strategy,
        amounts=lists(_amount_strategy, min_size=1, max_size=10),
    )
    @settings(max_examples=80)
    def test_sum_money_equals_sequential_addition(self, currency, amounts):
        """sum_money(moneys) == reduce(add, moneys) for same-currency lists."""
        moneys = [Money(amount=a, currency=currency) for a in amounts]
        via_sum = sum_money(moneys)
        via_reduce = moneys[0]
        for m in moneys[1:]:
            via_reduce = via_reduce + m
        assert via_sum == via_reduce
