"""Period-end revenue recognition job.

Runs IFRS 15 revenue recognition for a set of performance obligations
over a specified billing period.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from dinarledger.core.money import Money, zero
from dinarledger.core.types import BillingPeriod
from dinarledger.revenue.recognition import (
    PerformanceObligation,
    recognize_revenue,
)


@dataclass(frozen=True)
class RevenueRunSummary:
    """Summary of a revenue recognition job execution."""

    run_date: str
    obligations_processed: int
    total_recognized: Money
    zero_recognized_count: int

    def __str__(self) -> str:
        return (
            f"RevenueRun({self.run_date}: "
            f"{self.obligations_processed} obligations, "
            f"{self.total_recognized} recognized)"
        )


class RevenueJob:
    """Runs revenue recognition for a set of performance obligations.

    Parameters:
        obligations: Performance obligations to recognise.
        transaction_price: Total transaction price for the contract.
        period: Billing period over which to recognise revenue.
    """

    def __init__(
        self,
        obligations: list[PerformanceObligation] | None = None,
        transaction_price: Money | None = None,
        period: BillingPeriod | None = None,
    ) -> None:
        self._obligations = obligations or []
        self._transaction_price = transaction_price or zero("USD")
        self._period = period

    def run(self, current_time: datetime) -> RevenueRunSummary:
        """Execute revenue recognition.

        Returns a :class:`RevenueRunSummary`.
        """
        if not self._obligations or self._period is None:
            return RevenueRunSummary(
                run_date=current_time.date().isoformat(),
                obligations_processed=0,
                total_recognized=zero("USD"),
                zero_recognized_count=0,
            )

        results = recognize_revenue(
            self._obligations, self._transaction_price, self._period
        )

        currency = self._transaction_price.currency
        total = zero(currency)
        zero_count = 0

        for _, amount in results:
            if amount.is_zero():
                zero_count += 1
            total = total + amount

        return RevenueRunSummary(
            run_date=current_time.date().isoformat(),
            obligations_processed=len(results),
            total_recognized=total,
            zero_recognized_count=zero_count,
        )

    def __call__(self, current_time: datetime) -> RevenueRunSummary:
        """Scheduler-compatible entry point."""
        return self.run(current_time)

    def configure(
        self,
        obligations: list[PerformanceObligation],
        transaction_price: Money,
        period: BillingPeriod,
    ) -> None:
        """Set obligations and period for the next run."""
        self._obligations = obligations
        self._transaction_price = transaction_price
        self._period = period
