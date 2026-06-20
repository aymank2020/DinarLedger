#!/usr/bin/env python3
"""Payment reconciliation with bank statement entries.

Demonstrates:

1. Create multiple payments
2. Create bank statement entries (with slight timing differences)
3. Run reconciliation
4. Show matched / unmatched results
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from dinarledger.core.money import Money
from dinarledger.core.types import Payment, PaymentStatus
from dinarledger.payments.reconciliation import reconcile


def main() -> None:
    currency = "USD"

    # ── 1. Create payments ───────────────────────────────────────────────
    payments = [
        Payment(
            payment_id="pay-001",
            invoice_id="inv-001",
            amount=Money(Decimal("150.00"), currency),
            status=PaymentStatus.COMPLETED,
            paid_date=date(2025, 1, 10),
            reference="CUST-A-JAN",
        ),
        Payment(
            payment_id="pay-002",
            invoice_id="inv-002",
            amount=Money(Decimal("299.00"), currency),
            status=PaymentStatus.COMPLETED,
            paid_date=date(2025, 1, 12),
            reference="CUST-B-JAN",
        ),
        Payment(
            payment_id="pay-003",
            invoice_id="inv-003",
            amount=Money(Decimal("75.50"), currency),
            status=PaymentStatus.COMPLETED,
            paid_date=date(2025, 1, 15),
            reference="CUST-C-JAN",
        ),
        Payment(
            payment_id="pay-004",
            invoice_id="inv-004",
            amount=Money(Decimal("420.00"), currency),
            status=PaymentStatus.PENDING,
            paid_date=None,  # not yet received
            reference="CUST-D-JAN",
        ),
        Payment(
            payment_id="pay-005",
            invoice_id="inv-005",
            amount=Money(Decimal("199.00"), currency),
            status=PaymentStatus.COMPLETED,
            paid_date=date(2025, 1, 20),
            reference="CUST-E-JAN",
        ),
    ]

    # ── 2. Create bank statement entries ─────────────────────────────────
    # Some have slight date differences (clearing delay)
    bank_entries = [
        ("BNK-001", Money(Decimal("150.00"), currency), date(2025, 1, 10)),  # exact match
        ("BNK-002", Money(Decimal("299.00"), currency), date(2025, 1, 13)),  # 1 day later
        ("BNK-003", Money(Decimal("75.50"), currency), date(2025, 1, 16)),   # 1 day later
        ("BNK-004", Money(Decimal("199.00"), currency), date(2025, 1, 22)),  # 2 days later
        ("BNK-005", Money(Decimal("350.00"), currency), date(2025, 1, 25)),  # no matching payment
    ]

    # ── 3. Run reconciliation ────────────────────────────────────────────
    result = reconcile(payments, bank_entries)

    # ── 4. Show results ──────────────────────────────────────────────────
    print("=" * 60)
    print("PAYMENT RECONCILIATION REPORT")
    print("=" * 60)

    print(f"\nMatched payments ({len(result.matched)}):")
    for pay_id, bank_id in result.matched:
        print(f"  {pay_id} <-> {bank_id}")

    print(f"\nUnmatched payments ({len(result.unmatched_payments)}):")
    for pay_id in result.unmatched_payments:
        # Find the payment for context
        pay = next(p for p in payments if p.payment_id == pay_id)
        reason = "no paid_date (PENDING)" if pay.paid_date is None else "no matching bank entry"
        print(f"  {pay_id} — {reason}")

    print(f"\nUnmatched bank entries ({len(result.unmatched_bank)}):")
    for bank_id in result.unmatched_bank:
        entry = next(b for b in bank_entries if b[0] == bank_id)
        print(f"  {bank_id} — {entry[1]} on {entry[2]} (no matching payment)")

    print(f"\n{'─' * 60}")
    print("SUMMARY")
    print(f"{'─' * 60}")
    print(f"  Total payments:       {len(payments)}")
    print(f"  Total bank entries:   {len(bank_entries)}")
    print(f"  Matched:              {len(result.matched)}")
    print(f"  Unmatched payments:   {len(result.unmatched_payments)}")
    print(f"  Unmatched bank:       {len(result.unmatched_bank)}")
    match_rate = len(result.matched) / len(payments) * 100 if payments else 0
    print(f"  Match rate:           {match_rate:.0f}%")


if __name__ == "__main__":
    main()
