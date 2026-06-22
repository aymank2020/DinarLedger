"""Overdue invoice marker job.

Scans OPEN invoices and transitions those past their ``due_date`` to
``OVERDUE``.  Designed to run daily via the scheduler.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime

from dinarledger.core.enums import InvoiceStatus
from dinarledger.core.money import Money, zero
from dinarledger.core.types import Invoice


@dataclass(frozen=True)
class AgingRunSummary:
    """Summary of an aging job execution."""

    run_date: str
    invoices_scanned: int
    invoices_transitioned: int
    total_overdue_amount: Money

    def __str__(self) -> str:
        return (
            f"AgingRun({self.run_date}: "
            f"{self.invoices_transitioned} of {self.invoices_scanned} "
            f"transitioned to OVERDUE, {self.total_overdue_amount} overdue)"
        )


class AgingJob:
    """Marks OPEN invoices as OVERDUE when past their due date."""

    def run(
        self,
        invoices: list[Invoice],
        current_time: datetime,
    ) -> tuple[list[Invoice], AgingRunSummary]:
        """Scan *invoices* and transition overdue ones.

        Returns:
            A tuple of (updated invoices list, summary).
            The updated list is a new list with overdue invoices replaced
            by copies with ``status=OVERDUE``.
        """
        as_of = current_time.date()
        currency = "USD"
        for inv in invoices:
            if inv.line_items:
                currency = inv.line_items[0].amount.currency
                break

        scanned = 0
        transitioned = 0
        overdue_total = zero(currency)
        updated: list[Invoice] = []

        for inv in invoices:
            if inv.status == InvoiceStatus.OPEN:
                scanned += 1
                if inv.due_date < as_of:
                    updated.append(
                        replace(inv, status=InvoiceStatus.OVERDUE)
                    )
                    transitioned += 1
                    overdue_total = overdue_total + inv.total
                else:
                    updated.append(inv)
            else:
                updated.append(inv)

        summary = AgingRunSummary(
            run_date=as_of.isoformat(),
            invoices_scanned=scanned,
            invoices_transitioned=transitioned,
            total_overdue_amount=overdue_total,
        )
        return updated, summary

    def __call__(self, current_time: datetime) -> AgingRunSummary:
        """Scheduler-compatible entry point.

        Note: Requires invoices to be configured via :meth:`configure`.
        Returns an empty summary if not configured.
        """
        if not hasattr(self, "_invoices"):
            return AgingRunSummary(
                run_date=current_time.date().isoformat(),
                invoices_scanned=0,
                invoices_transitioned=0,
                total_overdue_amount=zero("USD"),
            )
        _, summary = self.run(self._invoices, current_time)
        self._invoices = _
        return summary

    def configure(self, invoices: list[Invoice]) -> None:
        """Set the invoices for scheduler-based execution."""
        self._invoices = list(invoices)
