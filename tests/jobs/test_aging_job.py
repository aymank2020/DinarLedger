"""Tests for the overdue invoice aging job."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from dinarledger.core.enums import InvoiceStatus
from dinarledger.core.money import Money
from dinarledger.core.types import BillingPeriod, Invoice, LineItem
from dinarledger.jobs.aging_job import AgingJob, AgingRunSummary


def _make_invoice(
    invoice_id: str = "inv-001",
    status: InvoiceStatus = InvoiceStatus.OPEN,
    due_date: date = date(2025, 1, 15),
    amount: Decimal = Decimal("100.00"),
) -> Invoice:
    return Invoice(
        invoice_id=invoice_id,
        customer_id="cust-001",
        issue_date=date(2025, 1, 1),
        due_date=due_date,
        line_items=[
            LineItem(description="Test charge", amount=Money(amount, "USD")),
        ],
        status=status,
    )


class TestAgingJob:
    def test_marks_overdue_invoice(self) -> None:
        job = AgingJob()
        inv = _make_invoice(due_date=date(2025, 1, 15))
        now = datetime(2025, 2, 1)  # well past due_date

        updated, summary = job.run([inv], now)
        assert summary.invoices_scanned == 1
        assert summary.invoices_transitioned == 1
        assert updated[0].status == InvoiceStatus.OVERDUE
        assert summary.total_overdue_amount == Money(Decimal("100.00"), "USD")

    def test_does_not_mark_current_invoice(self) -> None:
        job = AgingJob()
        inv = _make_invoice(due_date=date(2025, 2, 28))
        now = datetime(2025, 2, 1)  # not yet due

        updated, summary = job.run([inv], now)
        assert summary.invoices_transitioned == 0
        assert updated[0].status == InvoiceStatus.OPEN

    def test_does_not_mark_paid_invoice(self) -> None:
        job = AgingJob()
        inv = _make_invoice(status=InvoiceStatus.PAID, due_date=date(2025, 1, 15))
        now = datetime(2025, 2, 1)

        updated, summary = job.run([inv], now)
        assert summary.invoices_scanned == 0  # OPEN only
        assert summary.invoices_transitioned == 0

    def test_mixed_invoices(self) -> None:
        job = AgingJob()
        invoices = [
            _make_invoice("inv-1", InvoiceStatus.OPEN, date(2025, 1, 15)),  # overdue
            _make_invoice("inv-2", InvoiceStatus.OPEN, date(2025, 3, 1)),   # current
            _make_invoice("inv-3", InvoiceStatus.PAID, date(2025, 1, 15)),  # paid
            _make_invoice("inv-4", InvoiceStatus.OPEN, date(2025, 1, 10)),  # overdue
        ]
        now = datetime(2025, 2, 1)

        updated, summary = job.run(invoices, now)
        assert summary.invoices_scanned == 3  # only OPEN
        assert summary.invoices_transitioned == 2
        assert summary.total_overdue_amount == Money(Decimal("200.00"), "USD")

    def test_callable_without_configure(self) -> None:
        job = AgingJob()
        now = datetime(2025, 2, 1)
        summary = job(now)
        assert summary.invoices_scanned == 0

    def test_configure_and_call(self) -> None:
        job = AgingJob()
        inv = _make_invoice(due_date=date(2025, 1, 15))
        job.configure([inv])
        now = datetime(2025, 2, 1)
        summary = job(now)
        assert summary.invoices_transitioned == 1

    def test_exact_due_date_not_overdue(self) -> None:
        job = AgingJob()
        inv = _make_invoice(due_date=date(2025, 1, 15))
        now = datetime(2025, 1, 15)  # same day as due_date

        updated, summary = job.run([inv], now)
        assert summary.invoices_transitioned == 0  # due_date < as_of required
