"""Report service — orchestrates MRR breakdown, aging summaries,
deferred waterfalls, customer ledger, and revenue-by-period reports.

Delegates to:
* ``dinarledger.reports.mrr`` — MRR breakdown
* ``dinarledger.reports.aging`` — AR aging buckets
* ``dinarledger.reports.deferred_schedule`` — deferred waterfall
* ``dinarledger.customers.ledger`` — customer AR ledger
* ``dinarledger.revenue.recognition`` — revenue recognition
"""

from __future__ import annotations

from datetime import date
from typing import Any

from dinarledger.core.money import Money
from dinarledger.core.types import BillingPeriod, Invoice, Payment, Plan, Subscription
from dinarledger.reports.mrr import calculate_mrr as _calculate_mrr, MRRBreakdown
from dinarledger.reports.aging import aging_report as _aging_report, AgingBucket
from dinarledger.reports.deferred_schedule import (
    deferred_waterfall as _deferred_waterfall,
    WaterfallEntry,
)
from dinarledger.customers.ledger import (
    ledger_entry,
    customer_ledger_balance as _ledger_balance,
    aging_buckets as _aging_buckets,
)
from dinarledger.revenue.recognition import (
    PerformanceObligation,
    recognize_revenue as _recognize_revenue,
)


class ReportService:
    """Orchestrates all reporting operations.

    This service is stateless — operations delegate to domain modules
    and return plain data structures.
    """

    # ── MRR breakdown ───────────────────────────────────────────────────────

    def mrr_breakdown(
        self,
        subscriptions: list[Subscription],
        plans: dict[str, Plan],
        month: date,
    ) -> MRRBreakdown:
        """MRR movement breakdown for a single calendar month.

        Parameters
        ----------
        subscriptions : list[Subscription]
            All subscriptions to evaluate.
        plans : dict[str, Plan]
            Plans keyed by ``plan_id``.
        month : date
            Any date within the target month.

        Returns
        -------
        MRRBreakdown
        """
        return _calculate_mrr(subscriptions, plans, month)

    # ── Aging summary ───────────────────────────────────────────────────────

    def aging_summary(
        self,
        invoices: list[Invoice],
        as_of: date,
    ) -> list[AgingBucket]:
        """AR aging buckets from unpaid invoices.

        Returns
        -------
        list[AgingBucket]
        """
        return _aging_report(invoices, as_of)

    # ── Deferred waterfall ──────────────────────────────────────────────────

    def deferred_waterfall(
        self,
        obligations: list[PerformanceObligation],
        transaction_price: Money,
        start: date,
        end: date,
    ) -> list[WaterfallEntry]:
        """Monthly deferred revenue waterfall.

        Parameters
        ----------
        obligations : list[PerformanceObligation]
            Performance obligations in the contract.
        transaction_price : Money
            Total transaction price.
        start : date
            Start of the waterfall.
        end : date
            End of the waterfall.

        Returns
        -------
        list[WaterfallEntry]
        """
        return _deferred_waterfall(obligations, transaction_price, start)

    # ── Customer ledger ─────────────────────────────────────────────────────

    def customer_ledger(
        self,
        customer_id: str,
        invoices: list[Invoice],
        payments: list[Payment],
    ) -> dict[str, Any]:
        """Build a customer's AR transaction history.

        Parameters
        ----------
        customer_id : str
            Customer to report on.
        invoices : list[Invoice]
            All invoices for this customer.
        payments : list[Payment]
            All payments for this customer.

        Returns
        -------
        dict[str, Any]
            ``{"entries": [...], "balance": Money, "aging": dict}``
        """
        entries: list[ledger_entry] = []

        for inv in invoices:
            if inv.customer_id != customer_id:
                continue
            entries.append(
                ledger_entry(
                    date=inv.issue_date,
                    debit=inv.total,
                    reference=inv.invoice_id,
                )
            )

        for pay in payments:
            if pay.invoice_id and any(
                inv.invoice_id == pay.invoice_id and inv.customer_id == customer_id
                for inv in invoices
            ):
                entries.append(
                    ledger_entry(
                        date=pay.paid_date or date.today(),
                        credit=pay.amount,
                        reference=pay.payment_id,
                    )
                )

        entries.sort(key=lambda e: e.date)

        balance = _ledger_balance(entries)
        aging = _aging_buckets(entries, date.today())

        return {
            "entries": entries,
            "balance": balance,
            "aging": aging,
        }

    # ── Revenue by period ───────────────────────────────────────────────────

    def revenue_by_period(
        self,
        obligations: list[PerformanceObligation],
        transaction_price: Money,
        periods: list[BillingPeriod],
    ) -> list[tuple[BillingPeriod, list[tuple[str, Money]]]]:
        """Recognised revenue for each period in *periods*.

        Returns a list of ``(period, [(obligation_id, amount), ...])``
        tuples, one per period.
        """
        results: list[tuple[BillingPeriod, list[tuple[str, Money]]]] = []
        for period in periods:
            recognised = _recognize_revenue(obligations, transaction_price, period)
            results.append((period, recognised))
        return results
