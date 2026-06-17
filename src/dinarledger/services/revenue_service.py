"""Revenue service — orchestrates IFRS 15 revenue recognition,
deferred-revenue reporting, waterfall schedules, and bundle allocation.

Delegates to:
* ``dinarledger.revenue.recognition`` — recognize_revenue, calculate_deferred
* ``dinarledger.revenue.deferred`` — deferred_revenue_schedule
* ``dinarledger.revenue.allocation`` — allocate_transaction_price, residual_allocation
"""

from __future__ import annotations

from datetime import date
from typing import Any

from dinarledger.core.money import Money
from dinarledger.core.types import BillingPeriod
from dinarledger.revenue.recognition import (
    PerformanceObligation,
    recognize_revenue as _recognize_revenue,
    calculate_deferred as _calculate_deferred,
)
from dinarledger.revenue.deferred import (
    DeferredEntry,
    deferred_revenue_schedule as _deferred_schedule,
)
from dinarledger.revenue.allocation import (
    allocate_transaction_price as _allocate_proportional,
    residual_allocation as _allocate_residual,
)


class RevenueService:
    """Orchestrates revenue recognition workflows.

    This service is stateless — all operations are pure functions that
    delegate to the domain modules. It exists to provide a unified API
    for the application layer.
    """

    # ── Recognition ─────────────────────────────────────────────────────────

    def recognize_period(
        self,
        obligations: list[PerformanceObligation],
        transaction_price: Money,
        period: BillingPeriod,
    ) -> list[tuple[str, Money]]:
        """Recognise revenue for each obligation within *period*.

        Returns a list of ``(obligation_id, recognised_amount)`` tuples.
        """
        return _recognize_revenue(obligations, transaction_price, period)

    # ── Deferred summary ────────────────────────────────────────────────────

    def deferred_summary(
        self,
        obligations: list[PerformanceObligation],
        transaction_price: Money,
        as_of: date,
    ) -> Money:
        """Total deferred revenue across all obligations as of *as_of*."""
        return _calculate_deferred(obligations, transaction_price, as_of)

    # ── Waterfall schedule ──────────────────────────────────────────────────

    def waterfall_schedule(
        self,
        obligations: list[PerformanceObligation],
        transaction_price: Money,
        start: date,
        end: date,
    ) -> list[DeferredEntry]:
        """Monthly deferred-revenue roll-forward from *start* to *end*.

        Each entry contains beginning balance, recognised, additions,
        and ending balance.
        """
        return _deferred_schedule(obligations, transaction_price, start, end)

    # ── Bundle allocation ───────────────────────────────────────────────────

    def bundle_allocation(
        self,
        obligations: list[PerformanceObligation],
        total_price: Money,
        method: str = "proportional",
    ) -> list[tuple[PerformanceObligation, Money]]:
        """Allocate the transaction price across bundled obligations.

        Parameters
        ----------
        obligations : list[PerformanceObligation]
            Performance obligations in the bundle.
        total_price : Money
            Total transaction price to allocate.
        method : str
            ``"proportional"`` (default) allocates by standalone-selling-price
            ratio, or ``"residual"`` uses the IFRS 15 residual approach.

        Returns
        -------
        list[tuple[PerformanceObligation, Money]]
            Each obligation paired with its allocated amount.
        """
        if method == "residual":
            return _allocate_residual(obligations, total_price)
        if method == "proportional":
            return _allocate_proportional(obligations, total_price)

        raise ValueError(
            f"Unknown allocation method '{method}'; "
            "expected 'proportional' or 'residual'"
        )
