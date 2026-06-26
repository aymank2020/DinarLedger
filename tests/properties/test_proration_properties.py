"""Property-based tests for billing period and proration utilities.

Uses Hypothesis to verify invariants of proration_fraction, stub_period,
and billing_periods across a wide range of dates and configurations.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from hypothesis import given, assume, settings
from hypothesis.strategies import (
    builds,
    dates,
    integers,
    sampled_from,
    just,
    composite,
)

from dinarledger.core.types import BillingPeriod
from dinarledger.core.period import (
    proration_fraction,
    stub_period,
    billing_periods,
    days_in_period,
)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Reasonable date range for billing scenarios (year 2020–2030).
_date_strategy = dates(
    min_value=date(2020, 1, 1),
    max_value=date(2030, 12, 31),
)


@composite
def billing_period_strategy(draw):
    """Generate a valid BillingPeriod (start < end) using a single start
    date and an offset to guarantee validity."""
    start = draw(_date_strategy)
    extra = draw(integers(min_value=2, max_value=365))  # ≥2 ensures start < end
    end = start + timedelta(days=extra)
    return BillingPeriod(start_date=start, end_date=end)


# ---------------------------------------------------------------------------
# Tests: proration_fraction
# ---------------------------------------------------------------------------


class TestProrationFractionBounds:
    """proration_fraction always returns a value in [0, 1]."""

    @given(period=billing_period_strategy(), active_start=_date_strategy, active_end=_date_strategy)
    @settings(max_examples=120)
    def test_fraction_in_unit_interval(self, period, active_start, active_end):
        """Returned fraction is always between 0 and 1 inclusive."""
        frac = proration_fraction(period, active_start, active_end)
        assert Decimal("0") <= frac <= Decimal("1")

    @given(period=billing_period_strategy())
    @settings(max_examples=60)
    def test_full_overlap_gives_one(self, period):
        """When the active interval fully covers the period, fraction == 1."""
        # Active interval strictly wider than the period on both sides.
        active_start = period.start_date - timedelta(days=5)
        active_end = period.end_date + timedelta(days=5)
        frac = proration_fraction(period, active_start, active_end)
        assert frac == Decimal("1")

    @given(period=billing_period_strategy())
    @settings(max_examples=60)
    def test_exact_overlap_gives_one(self, period):
        """When the active interval equals the period exactly, fraction == 1."""
        frac = proration_fraction(period, period.start_date, period.end_date)
        assert frac == Decimal("1")

    @given(period=billing_period_strategy())
    @settings(max_examples=60)
    def test_no_overlap_before_gives_zero(self, period):
        """Active interval entirely before the period yields fraction 0."""
        active_end = period.start_date - timedelta(days=1)
        active_start = active_end - timedelta(days=30)
        frac = proration_fraction(period, active_start, active_end)
        assert frac == Decimal("0")

    @given(period=billing_period_strategy())
    @settings(max_examples=60)
    def test_no_overlap_after_gives_zero(self, period):
        """Active interval entirely after the period yields fraction 0."""
        active_start = period.end_date + timedelta(days=1)
        active_end = active_start + timedelta(days=30)
        frac = proration_fraction(period, active_start, active_end)
        assert frac == Decimal("0")


class TestProrationSymmetry:
    """Symmetry properties of proration_fraction."""

    @given(period=billing_period_strategy(), offset_start=integers(min_value=0, max_value=180),
           offset_end=integers(min_value=0, max_value=180))
    @settings(max_examples=80)
    def test_overlap_from_start_symmetry(self, period, offset_start, offset_end):
        """Overlapping the same number of days from start and end gives
        the same fraction when the period has uniform day-count."""
        # Create two active intervals: one clipped to the start, one to the end.
        days_in = period.days

        # Clip offsets so we don't exceed the period.
        s_off = min(offset_start, days_in - 1)
        e_off = min(offset_end, days_in - 1)

        active_from_start = (period.start_date, period.start_date + timedelta(days=s_off))
        active_from_end = (period.end_date - timedelta(days=e_off), period.end_date)

        frac_start = proration_fraction(period, *active_from_start)
        frac_end = proration_fraction(period, *active_from_end)

        # If both intervals overlap the same number of days they should have
        # the same fraction (since total days in period is the denominator).
        if s_off == e_off:
            assert frac_start == frac_end


# ---------------------------------------------------------------------------
# Tests: stub_period
# ---------------------------------------------------------------------------


class TestStubPeriodProperties:
    """stub_period always returns a valid BillingPeriod or None."""

    @given(period=billing_period_strategy(), eff_date=_date_strategy)
    @settings(max_examples=100)
    def test_stub_is_valid_period_or_none(self, period, eff_date):
        """stub_period returns either None or a BillingPeriod with start <= end."""
        stub = stub_period(period, eff_date)
        if stub is None:
            # None means effective_date was at or after period end.
            assert eff_date >= period.end_date
        else:
            assert stub.start_date <= stub.end_date
            assert stub.start_date >= period.start_date
            assert stub.end_date == period.end_date

    @given(period=billing_period_strategy())
    @settings(max_examples=60)
    def test_stub_before_period_start_returns_full_period(self, period):
        """When effective_date <= period.start_date, stub is the full period."""
        eff = period.start_date - timedelta(days=10)
        stub = stub_period(period, eff)
        assert stub is not None
        assert stub.start_date == period.start_date
        assert stub.end_date == period.end_date

    @given(period=billing_period_strategy())
    @settings(max_examples=60)
    def test_stub_after_period_end_returns_none(self, period):
        """When effective_date > period.end_date, stub returns None."""
        eff = period.end_date + timedelta(days=1)
        stub = stub_period(period, eff)
        assert stub is None


# ---------------------------------------------------------------------------
# Tests: billing_periods
# ---------------------------------------------------------------------------


class TestBillingPeriodsProperties:
    """billing_periods returns the correct number of contiguous periods."""

    @given(
        start=_date_strategy,
        cycles=integers(min_value=1, max_value=12),
        cycle=sampled_from(["monthly", "quarterly", "annual"]),
    )
    @settings(max_examples=80)
    def test_billing_periods_returns_correct_count(self, start, cycles, cycle):
        """The number of returned periods equals *cycles*."""
        periods = billing_periods(start, cycles, cycle)
        assert len(periods) == cycles

    @given(
        start=_date_strategy,
        cycles=integers(min_value=2, max_value=6),
        cycle=sampled_from(["monthly", "quarterly", "annual"]),
    )
    @settings(max_examples=60)
    def test_billing_periods_are_contiguous(self, start, cycles, cycle):
        """Each period's end_date + 1 day equals the next period's start_date."""
        periods = billing_periods(start, cycles, cycle)
        for i in range(len(periods) - 1):
            assert periods[i].end_date + timedelta(days=1) == periods[i + 1].start_date

    @given(
        start=_date_strategy,
        cycles=integers(min_value=1, max_value=4),
        cycle=sampled_from(["monthly", "quarterly", "annual"]),
    )
    @settings(max_examples=60)
    def test_billing_periods_have_positive_duration(self, start, cycles, cycle):
        """Every generated period spans at least one day."""
        periods = billing_periods(start, cycles, cycle)
        for p in periods:
            assert p.start_date < p.end_date
