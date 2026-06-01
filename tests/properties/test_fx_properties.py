"""Property-based tests for FX rate operations and currency conversion.

Uses Hypothesis to verify round-trip consistency, double-inversion
stability, and cross-rate coherence of the dinarledger.fx.rates module.
"""

from datetime import date
from decimal import Decimal, ROUND_HALF_UP

import pytest
from hypothesis import given, assume, settings
from hypothesis.strategies import (
    builds,
    decimals,
    dates,
    sampled_from,
    just,
)

from dinarledger.core.money import Money
from dinarledger.fx.rates import FXRate, convert, cross_rate


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Positive exchange rates — minimum 0.1 avoids extreme quantization loss
# when amounts are small.
_positive_rate = decimals(
    min_value=Decimal("0.1"),
    max_value=Decimal("100"),
    places=4,
    allow_nan=False,
    allow_infinity=False,
)

# Reasonable date range.
_date_strategy = dates(
    min_value=date(2022, 1, 1),
    max_value=date(2028, 12, 31),
)

# Amounts in source currency — large enough that quantization to 0.01
# introduces only a small relative error.
_amount_strategy = decimals(
    min_value=Decimal("10"),
    max_value=Decimal("1000000"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

_CURRENCIES = ["USD", "EUR", "GBP", "KWD", "JPY", "SAR", "CHF", "CAD"]


# ---------------------------------------------------------------------------
# Tests: convert then invert round-trip
# ---------------------------------------------------------------------------


class TestConvertRoundTrip:
    """Converting then converting back should approximately recover the
    original amount (within rounding tolerance)."""

    @given(
        amount=_amount_strategy,
        rate_val=_positive_rate,
        rate_date=_date_strategy,
    )
    @settings(max_examples=80)
    def test_convert_then_invert_approx_original(self, amount, rate_val, rate_date):
        """convert(convert(m, target, rate), source, 1/rate) ≈ m."""
        source = "USD"
        target = "EUR"
        m = Money(amount=amount, currency=source)
        fx = FXRate(base=source, quote=target, rate=rate_val, rate_date=rate_date)

        # Forward conversion
        converted = convert(m, target, fx.rate)
        assert converted.currency == target

        # Reverse conversion using the inverted rate
        inverted_fx = fx.invert()
        round_tripped = convert(converted, source, inverted_fx.rate)
        assert round_tripped.currency == source

        # Tolerance accounts for two quantization steps (each to 0.01)
        # plus the 6-decimal quantization on the inverted rate.
        # Forward step loses at most 0.005; reverse amplifies by ~1/rate
        # and loses another 0.005. For rates ≥ 0.1 this is bounded.
        tolerance = Decimal("0.05") * max(abs(amount), Decimal("1"))
        assert abs(round_tripped.amount - amount) <= tolerance, (
            f"round-trip {amount} → {converted.amount} → {round_tripped.amount}, "
            f"tolerance {tolerance}"
        )

    @given(
        amount=_amount_strategy,
        rate_val=_positive_rate,
        rate_date=_date_strategy,
    )
    @settings(max_examples=60)
    def test_converted_amount_non_negative(self, amount, rate_val, rate_date):
        """Forward conversion of a positive amount yields a non-negative amount."""
        m = Money(amount=amount, currency="USD")
        fx = FXRate(base="USD", quote="EUR", rate=rate_val, rate_date=rate_date)
        converted = convert(m, "EUR", fx.rate)
        assert converted.amount >= Decimal("0")

    @given(
        amount=_amount_strategy,
        rate_val=_positive_rate,
        rate_date=_date_strategy,
    )
    @settings(max_examples=60)
    def test_converted_amount_positive_for_reasonable_inputs(
        self, amount, rate_val, rate_date
    ):
        """Forward conversion of a positive amount with a reasonable rate
        yields a positive amount (not quantized to zero)."""
        m = Money(amount=amount, currency="USD")
        fx = FXRate(base="USD", quote="EUR", rate=rate_val, rate_date=rate_date)
        converted = convert(m, "EUR", fx.rate)
        assert converted.amount > Decimal("0")


# ---------------------------------------------------------------------------
# Tests: double inversion
# ---------------------------------------------------------------------------


class TestDoubleInversion:
    """FXRate.invert().invert() should approximate the original rate."""

    @given(rate_val=_positive_rate, rate_date=_date_strategy)
    @settings(max_examples=80)
    def test_double_invert_approx_original_rate(self, rate_val, rate_date):
        """invert(invert(r)).rate ≈ r.rate (within quantisation tolerance)."""
        fx = FXRate(base="USD", quote="EUR", rate=rate_val, rate_date=rate_date)
        double_inverted = fx.invert().invert()

        # The rate is quantized to 6 decimal places on each invert.
        # Two inversions can introduce error proportional to rate^2 * ULP
        # where ULP = 0.000001. We use a proportional tolerance.
        tolerance = Decimal("0.01") * max(abs(rate_val), Decimal("1"))
        assert abs(double_inverted.rate - rate_val) <= tolerance, (
            f"double invert: {rate_val} → {fx.invert().rate} → "
            f"{double_inverted.rate}, diff {abs(double_inverted.rate - rate_val)}"
        )

    @given(rate_val=_positive_rate, rate_date=_date_strategy)
    @settings(max_examples=60)
    def test_double_invert_restores_currency_pair(self, rate_val, rate_date):
        """invert(invert(r)) restores the original base and quote."""
        fx = FXRate(base="USD", quote="EUR", rate=rate_val, rate_date=rate_date)
        double_inverted = fx.invert().invert()
        assert double_inverted.base == fx.base
        assert double_inverted.quote == fx.quote

    @given(rate_val=_positive_rate, rate_date=_date_strategy)
    @settings(max_examples=60)
    def test_single_invert_swaps_pair(self, rate_val, rate_date):
        """invert() swaps base and quote currencies."""
        fx = FXRate(base="USD", quote="EUR", rate=rate_val, rate_date=rate_date)
        inv = fx.invert()
        assert inv.base == "EUR"
        assert inv.quote == "USD"

    @given(rate_val=_positive_rate, rate_date=_date_strategy)
    @settings(max_examples=60)
    def test_invert_reciprocal(self, rate_val, rate_date):
        """invert().rate ≈ 1 / original rate (within quantisation)."""
        fx = FXRate(base="USD", quote="EUR", rate=rate_val, rate_date=rate_date)
        inv = fx.invert()
        expected = (Decimal("1") / rate_val).quantize(
            Decimal("0.000001"), rounding=ROUND_HALF_UP
        )
        assert inv.rate == expected


# ---------------------------------------------------------------------------
# Tests: cross_rate consistency
# ---------------------------------------------------------------------------


class TestCrossRateConsistency:
    """cross_rate should be consistent: A→C via B equals A→B × B→C."""

    @given(
        rate_ab_val=_positive_rate,
        rate_bc_val=_positive_rate,
        rate_date=_date_strategy,
    )
    @settings(max_examples=60)
    def test_cross_rate_via_common_base(self, rate_ab_val, rate_bc_val, rate_date):
        """Given USD→EUR and EUR→GBP (common base=quote), cross_rate gives
        A→C = rate_AB * rate_BC."""
        fx_ab = FXRate(base="USD", quote="EUR", rate=rate_ab_val, rate_date=rate_date)
        fx_bc = FXRate(base="EUR", quote="GBP", rate=rate_bc_val, rate_date=rate_date)

        cross = cross_rate(fx_ab, fx_bc)

        # When rate1.quote == rate2.base, cross = rate1.rate * rate2.rate
        expected = (rate_ab_val * rate_bc_val).quantize(
            Decimal("0.000001"), rounding=ROUND_HALF_UP
        )
        assert cross == expected, f"cross_rate={cross}, expected={expected}"

    @given(
        rate_ab_val=_positive_rate,
        rate_bc_val=_positive_rate,
        rate_date=_date_strategy,
    )
    @settings(max_examples=60)
    def test_cross_rate_via_common_quote(self, rate_ab_val, rate_bc_val, rate_date):
        """Given USD→EUR and GBP→EUR (common quote), cross_rate gives a
        result consistent with inverting one leg first."""
        fx_ab = FXRate(base="USD", quote="EUR", rate=rate_ab_val, rate_date=rate_date)
        fx_bc = FXRate(base="GBP", quote="EUR", rate=rate_bc_val, rate_date=rate_date)

        cross = cross_rate(fx_ab, fx_bc)

        # When rate1.quote == rate2.quote, cross_rate inverts rate1 and
        # multiplies. We replicate that exact logic here:
        inv_rate = (Decimal("1") / rate_ab_val).quantize(
            Decimal("0.000001"), rounding=ROUND_HALF_UP
        )
        expected = (inv_rate * rate_bc_val).quantize(
            Decimal("0.000001"), rounding=ROUND_HALF_UP
        )
        assert cross == expected, f"cross_rate={cross}, expected={expected}"

    @given(
        rate_ab_val=_positive_rate,
        rate_bc_val=_positive_rate,
        rate_date=_date_strategy,
    )
    @settings(max_examples=60)
    def test_cross_rate_conversion_consistent(self, rate_ab_val, rate_bc_val, rate_date):
        """Converting USD→EUR→GBP via individual rates should be close to
        converting USD→GBP using the cross rate."""
        fx_ab = FXRate(base="USD", quote="EUR", rate=rate_ab_val, rate_date=rate_date)
        fx_bc = FXRate(base="EUR", quote="GBP", rate=rate_bc_val, rate_date=rate_date)

        original = Money(amount=Decimal("100.00"), currency="USD")

        # Step-by-step conversion
        in_eur = convert(original, "EUR", fx_ab.rate)
        in_gbp_stepwise = convert(in_eur, "GBP", fx_bc.rate)

        # Cross-rate conversion
        cross = cross_rate(fx_ab, fx_bc)
        in_gbp_cross = convert(original, "GBP", cross)

        # The two approaches may differ by at most 0.01 per quantization step.
        # Stepwise has two rounding steps; cross has one. Tolerance of 0.02
        # covers the worst case.
        tolerance = Decimal("0.02")
        assert abs(in_gbp_cross.amount - in_gbp_stepwise.amount) <= tolerance, (
            f"cross={in_gbp_cross.amount}, stepwise={in_gbp_stepwise.amount}"
        )
