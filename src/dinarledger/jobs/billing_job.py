"""Monthly billing cycle job.

Generates invoices for all active subscriptions in a given billing period.
Designed to be run by the tick-based scheduler at the start of each month.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from dinarledger.core.money import Money, zero
from dinarledger.core.types import (
    BillingPeriod,
    Invoice,
    Subscription,
    TaxRate,
)
from dinarledger.billing.invoice_gen import generate_invoice


@dataclass(frozen=True)
class BillingRunSummary:
    """Summary of a billing job execution."""

    run_date: date
    invoices_generated: int
    invoices_skipped: int
    total_amount: Money
    errors: int

    def __str__(self) -> str:
        return (
            f"BillingRun({self.run_date.isoformat()}: "
            f"{self.invoices_generated} invoices, "
            f"{self.total_amount} total, "
            f"{self.errors} errors)"
        )


class BillingJob:
    """Generates invoices for all active subscriptions.

    Parameters:
        tax_rates: Tax rate definitions keyed by tax code.
        tax_code: Default tax code applied to invoice line items.
    """

    def __init__(
        self,
        tax_rates: dict[str, TaxRate] | None = None,
        tax_code: str = "",
    ) -> None:
        self._tax_rates = tax_rates or {}
        self._tax_code = tax_code

    def run(
        self,
        subscriptions: list[Subscription],
        period: BillingPeriod,
        current_time: datetime,
    ) -> BillingRunSummary:
        """Generate invoices for all active subscriptions.

        Returns a :class:`BillingRunSummary` with counts and totals.
        """
        currency = "USD"
        total = zero(currency)
        generated = 0
        skipped = 0
        errors = 0
        invoices: list[Invoice] = []

        for sub in subscriptions:
            try:
                inv = generate_invoice(
                    subscription=sub,
                    period=period,
                    tax_rates=self._tax_rates,
                    tax_code=self._tax_code,
                )
                if inv is None:
                    skipped += 1
                else:
                    generated += 1
                    total = total + inv.total
                    invoices.append(inv)
            except Exception:
                errors += 1

        return BillingRunSummary(
            run_date=period.start_date,
            invoices_generated=generated,
            invoices_skipped=skipped,
            total_amount=total,
            errors=errors,
        )

    def __call__(self, current_time: datetime) -> BillingRunSummary:
        """Scheduler-compatible entry point.

        Note: When used directly with the scheduler, subscriptions and
        period must be set beforehand via :meth:`configure`.  If not
        configured, returns an empty summary.
        """
        if not hasattr(self, "_subscriptions") or not hasattr(self, "_period"):
            return BillingRunSummary(
                run_date=current_time.date(),
                invoices_generated=0,
                invoices_skipped=0,
                total_amount=zero("USD"),
                errors=0,
            )
        return self.run(self._subscriptions, self._period, current_time)

    def configure(
        self,
        subscriptions: list[Subscription],
        period: BillingPeriod,
    ) -> None:
        """Set the subscriptions and period for scheduler-based execution."""
        self._subscriptions = subscriptions
        self._period = period
