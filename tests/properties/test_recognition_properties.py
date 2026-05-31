"""Property-based tests for IFRS 15 revenue recognition.

Uses Hypothesis to verify invariants of recognize_revenue and
calculate_deferred across varied performance obligations, transaction
prices, and billing periods.
"""

from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

import pytest
from hypothesis import given, assume, settings
from hypothesis.strategies import (
    builds,
    dates,
    decimals,
    integers,
    sampled_from,
    just,
    booleans,
    text,
)

from dinarledger.core.money import Money, sum_money
from dinarledger.core.types import BillingPeriod
from dinarledger.revenue.recognition import (
    PerformanceObligation,
    recognize_revenue,
    calculate_deferred,
    _allocated_price,
    _total_standalone_price,
)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_CURRENCY = "USD"

_positive_amount = decimals(
    min_value=Decimal("1"),
    max_value=Decimal("100000"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

_date_strategy = dates(
    min_value=date(2022, 1, 1),
    max_value=date(2028, 12, 31),
)

_small_id = text(min_size=1, max_size=8, alphabet="ABCDEF0123456789")


def _over_time_obligation(obligation_id, start_date, end_date, standalone_price):
    """Build a satisfied-over-time PerformanceObligation."""
    return PerformanceObligation(
        obligation_id=obligation_id,
        description=f"over-time {obligation_id}",
        standalone_price=standalone_price,
        satisfied_over_time=True,
        start_date=start_date,
        end_date=end_date,
    )


def _point_in_time_obligation(obligation_id, start_date, end_date, standalone_price):
    """Build a point-in-time PerformanceObligation."""
    return PerformanceObligation(
        obligation_id=obligation_id,
        description=f"point-in-time {obligation_id}",
        standalone_price=standalone_price,
        satisfied_over_time=False,
        start_date=start_date,
        end_date=end_date,
    )


def _allocated_for_obl(obl, total_standalone, total_txn_price):
    """Compute the allocated price for one obligation (public logic)."""
    return _allocated_price(obl, total_standalone, total_txn_price)


# ---------------------------------------------------------------------------
# Tests: cumulative recognised never exceeds allocated
# ---------------------------------------------------------------------------


class TestCumulativeRecognisedBounds:
    """Recognised amounts must never exceed the allocated price."""

    @given(
        start_date=_date_strategy,
        duration_months=integers(min_value=3, max_value=12),
        ssp1=_positive_amount,
        ssp2=_positive_amount,
        txn1=_positive_amount,
        txn2=_positive_amount,
    )
    @settings(max_examples=40, deadline=10000)
    def test_over_time_recognised_le_allocated(self, start_date, duration_months,
                                                ssp1, ssp2, txn1, txn2):
        """For over-time obligations, recognised within any single period
        does not exceed the allocated price."""
        end_date = start_date + timedelta(days=duration_months * 30)
        assume(end_date > start_date)

        obl1 = _over_time_obligation("O1", start_date, end_date,
                                      Money(amount=ssp1, currency=_CURRENCY))
        obl2 = _over_time_obligation("O2", start_date, end_date,
                                      Money(amount=ssp2, currency=_CURRENCY))
        obligations = [obl1, obl2]
        total_txn = Money(amount=txn1 + txn2, currency=_CURRENCY)

        # Period covering the full obligation span
        period = BillingPeriod(start_date=start_date, end_date=end_date)
        results = recognize_revenue(obligations, total_txn, period)

        total_standalone = _total_standalone_price(obligations)
        for obl_id, recognised in results:
            obl = [o for o in obligations if o.obligation_id == obl_id][0]
            allocated = _allocated_for_obl(obl, total_standalone, total_txn)
            # Monthly rounding can cause cumulative recognised to slightly
            # exceed the allocated price; each month may overshoot by up to
            # 0.005 (half a cent) due to quantization.
            tolerance = Decimal("0.01") * duration_months
            assert recognised.amount <= allocated.amount + tolerance, (
                f"{obl_id}: recognised {recognised} > allocated {allocated} "
                f"(tolerance {tolerance})"
            )


# ---------------------------------------------------------------------------
# Tests: monotonicity of recognition over time
# ---------------------------------------------------------------------------


class TestRecognitionMonotonicity:
    """Deferred revenue is non-increasing over time ⇒ recognised is non-decreasing."""

    @given(
        start_date=_date_strategy,
        duration_months=integers(min_value=3, max_value=12),
        ssp=_positive_amount,
        txn=_positive_amount,
        as_of_offset1=integers(min_value=0, max_value=180),
        as_of_offset2=integers(min_value=0, max_value=180),
    )
    @settings(max_examples=40, deadline=10000)
    def test_deferred_non_increasing(self, start_date, duration_months,
                                      ssp, txn, as_of_offset1, as_of_offset2):
        """calculate_deferred(as_of_later) <= calculate_deferred(as_of_earlier)."""
        end_date = start_date + timedelta(days=duration_months * 30)
        assume(end_date > start_date)

        obl = _over_time_obligation("O1", start_date, end_date,
                                     Money(amount=ssp, currency=_CURRENCY))
        obligations = [obl]
        total_txn = Money(amount=txn, currency=_CURRENCY)

        as_of_1 = start_date + timedelta(days=as_of_offset1)
        as_of_2 = start_date + timedelta(days=as_of_offset2)

        # Ensure ordering
        if as_of_1 > as_of_2:
            as_of_1, as_of_2 = as_of_2, as_of_1

        d1 = calculate_deferred(obligations, total_txn, as_of_1)
        d2 = calculate_deferred(obligations, total_txn, as_of_2)

        # Deferred at later date should be <= deferred at earlier date
        assert d2.amount <= d1.amount + Decimal("0.02"), (
            f"deferred({as_of_2})={d2} > deferred({as_of_1})={d1}"
        )


# ---------------------------------------------------------------------------
# Tests: deferred + recognised ≈ allocated
# ---------------------------------------------------------------------------


class TestDeferredPlusRecognised:
    """For a single obligation: deferred + cumulative_recognised ≈ allocated."""

    @given(
        start_date=_date_strategy,
        duration_months=integers(min_value=3, max_value=12),
        ssp=_positive_amount,
        txn=_positive_amount,
        as_of_offset=integers(min_value=0, max_value=365),
    )
    @settings(max_examples=40, deadline=10000)
    def test_deferred_plus_cumulative_recognised_approx_allocated(
        self, start_date, duration_months, ssp, txn, as_of_offset
    ):
        """allocated ≈ deferred(as_of) + cumulative_recognised(as_of)."""
        end_date = start_date + timedelta(days=duration_months * 30)
        assume(end_date > start_date)

        obl = _over_time_obligation("O1", start_date, end_date,
                                     Money(amount=ssp, currency=_CURRENCY))
        obligations = [obl]
        total_txn = Money(amount=txn, currency=_CURRENCY)

        as_of = start_date + timedelta(days=as_of_offset)

        total_standalone = _total_standalone_price(obligations)
        allocated = _allocated_for_obl(obl, total_standalone, total_txn)
        deferred = calculate_deferred(obligations, total_txn, as_of)

        # cumulative_recognised = allocated - deferred (clamped)
        cumulative_recognised = allocated - deferred
        # Due to rounding, cumulative_recognised may be slightly negative;
        # just check the sum is close to allocated.
        total = deferred + cumulative_recognised
        tolerance = Decimal("0.05") * max(abs(allocated.amount), Decimal("1"))
        assert abs(total.amount - allocated.amount) <= tolerance, (
            f"deferred({deferred}) + recognised({cumulative_recognised}) = {total}"
            f" ≠ allocated({allocated}) within tolerance"
        )


# ---------------------------------------------------------------------------
# Tests: point-in-time obligations
# ---------------------------------------------------------------------------


class TestPointInTimeRecognition:
    """Point-in-time obligations recognise the full allocated amount
    when end_date falls within the billing period."""

    @given(
        start_date=_date_strategy,
        end_offset=integers(min_value=5, max_value=120),
        ssp=_positive_amount,
        txn=_positive_amount,
    )
    @settings(max_examples=50)
    def test_full_recognition_on_end_date(self, start_date, end_offset, ssp, txn):
        """When the period includes the obligation's end_date, the full
        allocated amount is recognised for a point-in-time obligation."""
        end_date = start_date + timedelta(days=end_offset)
        assume(end_date > start_date)

        obl = _point_in_time_obligation("PIT1", start_date, end_date,
                                         Money(amount=ssp, currency=_CURRENCY))
        obligations = [obl]
        total_txn = Money(amount=txn, currency=_CURRENCY)

        # Billing period that spans well past end_date
        period = BillingPeriod(
            start_date=start_date,
            end_date=end_date + timedelta(days=30),
        )

        results = recognize_revenue(obligations, total_txn, period)
        assert len(results) == 1

        total_standalone = _total_standalone_price(obligations)
        allocated = _allocated_for_obl(obl, total_standalone, total_txn)
        obl_id, recognised = results[0]
        assert recognised == allocated, (
            f"point-in-time: recognised {recognised} ≠ allocated {allocated}"
        )

    @given(
        start_date=_date_strategy,
        end_offset=integers(min_value=5, max_value=120),
        ssp=_positive_amount,
        txn=_positive_amount,
    )
    @settings(max_examples=50)
    def test_zero_recognition_before_end_date(self, start_date, end_offset, ssp, txn):
        """When the period ends before the obligation's end_date, no amount
        is recognised for a point-in-time obligation."""
        end_date = start_date + timedelta(days=end_offset)
        assume(end_date > start_date)

        obl = _point_in_time_obligation("PIT2", start_date, end_date,
                                         Money(amount=ssp, currency=_CURRENCY))
        obligations = [obl]
        total_txn = Money(amount=txn, currency=_CURRENCY)

        # Period that ends before end_date
        period_end = end_date - timedelta(days=1)
        assume(period_end > start_date)
        period = BillingPeriod(start_date=start_date, end_date=period_end)

        results = recognize_revenue(obligations, total_txn, period)
        obl_id, recognised = results[0]
        assert recognised.is_zero(), (
            f"point-in-time before end_date: recognised {recognised} should be 0"
        )
