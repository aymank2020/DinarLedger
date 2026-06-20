#!/usr/bin/env python3
"""IFRS 15 SSP allocation for a bundled contract.

Demonstrates:

1. Create a bundle (SaaS + onboarding + support)
2. Define performance obligations with standalone selling prices (SSPs)
3. Allocate transaction price using proportional and residual methods
4. Generate a revenue recognition schedule
5. Print monthly recognized revenue
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from dinarledger.core.money import Money
from dinarledger.core.types import BillingPeriod
from dinarledger.revenue.recognition import (
    PerformanceObligation,
    recognize_revenue,
    calculate_deferred,
)
from dinarledger.revenue.allocation import (
    allocate_transaction_price,
    residual_allocation,
)
from dinarledger.revenue.deferred import deferred_revenue_schedule


def main() -> None:
    # ── 1. Define the bundle ─────────────────────────────────────────────
    contract_start = date(2025, 1, 1)
    contract_end = date(2025, 12, 31)
    currency = "USD"

    # ── 2. Performance obligations with SSPs ─────────────────────────────
    obligations = [
        PerformanceObligation(
            obligation_id="saas",
            description="SaaS Platform Access",
            standalone_price=Money(Decimal("1200.00"), currency),
            satisfied_over_time=True,
            start_date=contract_start,
            end_date=contract_end,
        ),
        PerformanceObligation(
            obligation_id="onboarding",
            description="Implementation & Onboarding",
            standalone_price=Money(Decimal("3000.00"), currency),
            satisfied_over_time=False,
            start_date=contract_start,
            end_date=date(2025, 3, 31),  # delivered by end of Q1
        ),
        PerformanceObligation(
            obligation_id="support",
            description="Premium Support",
            standalone_price=Money(Decimal("600.00"), currency),
            satisfied_over_time=True,
            start_date=contract_start,
            end_date=contract_end,
        ),
    ]

    total_ssp = sum(o.standalone_price.amount for o in obligations)
    print("=" * 70)
    print("IFRS 15 SSP ALLOCATION — BUNDLE ANALYSIS")
    print("=" * 70)
    print(f"\nContract period: {contract_start} to {contract_end}")
    print(f"\nPerformance Obligations & SSPs:")
    for obl in obligations:
        tag = "over-time" if obl.satisfied_over_time else "point-in-time"
        print(f"  {obl.obligation_id:>12}: {obl.standalone_price} ({tag})")
    print(f"  {'Total SSP':>12}: {Money(total_ssp, currency)}")

    # ── 3. Allocate transaction price ────────────────────────────────────
    # The customer negotiated a 10% discount: total = 4,320 instead of 4,800
    transaction_price = Money(Decimal("4320.00"), currency)
    print(f"\n  Transaction price: {transaction_price}")
    print(f"  Discount:          {Money(total_ssp - transaction_price.amount, currency)}")

    # 3a. Proportional allocation
    proportional = allocate_transaction_price(obligations, transaction_price)
    print(f"\n{'─' * 70}")
    print("PROPORTIONAL ALLOCATION (SSP ratio)")
    print(f"{'─' * 70}")
    for obl, allocated in proportional:
        pct = (obl.standalone_price.amount / total_ssp) * 100
        print(f"  {obl.obligation_id:>12}: {allocated} ({pct:.1f}% of SSP)")
    total_allocated = sum(a.amount for _, a in proportional)
    print(f"  {'Total allocated':>12}: {Money(total_allocated, currency)}")

    # 3b. Residual allocation (one obligation with uncertain SSP)
    obligations_with_uncertain = [
        PerformanceObligation(
            obligation_id="saas",
            description="SaaS Platform Access",
            standalone_price=Money(Decimal("1200.00"), currency),
            satisfied_over_time=True,
            start_date=contract_start,
            end_date=contract_end,
        ),
        PerformanceObligation(
            obligation_id="onboarding",
            description="Implementation & Onboarding",
            standalone_price=Money(Decimal("3000.00"), currency),
            satisfied_over_time=False,
            start_date=contract_start,
            end_date=date(2025, 3, 31),
        ),
        PerformanceObligation(
            obligation_id="support",
            description="Premium Support (SSP uncertain)",
            standalone_price=Money(Decimal("0"), currency),  # uncertain SSP
            satisfied_over_time=True,
            start_date=contract_start,
            end_date=contract_end,
        ),
    ]
    residual = residual_allocation(obligations_with_uncertain, transaction_price)
    print(f"\n{'─' * 70}")
    print("RESIDUAL ALLOCATION (uncertain SSP for support)")
    print(f"{'─' * 70}")
    for obl, allocated in residual:
        ssp_label = f"(SSP: {obl.standalone_price})" if not obl.standalone_price.is_zero() else "(SSP: uncertain)"
        print(f"  {obl.obligation_id:>12}: {allocated} {ssp_label}")
    total_residual = sum(a.amount for _, a in residual)
    print(f"  {'Total allocated':>12}: {Money(total_residual, currency)}")

    # ── 4. Revenue recognition schedule (proportional allocation) ─────────
    print(f"\n{'─' * 70}")
    print("MONTHLY REVENUE RECOGNITION SCHEDULE")
    print(f"{'─' * 70}")

    schedule = deferred_revenue_schedule(
        obligations, transaction_price, contract_start, contract_end
    )

    print(f"{'Month':>10}  {'Beg Bal':>12}  {'Recognized':>12}  {'Additions':>12}  {'End Bal':>12}")
    print("-" * 70)
    for entry in schedule:
        month_label = entry.date.strftime("%b %Y")
        print(
            f"{month_label:>10}  {entry.beginning_balance.amount:>12.2f}  "
            f"{entry.recognized.amount:>12.2f}  {entry.additions.amount:>12.2f}  "
            f"{entry.ending_balance.amount:>12.2f}"
        )

    # ── 5. Deferred revenue at mid-year ──────────────────────────────────
    mid_year = date(2025, 6, 30)
    deferred_mid = calculate_deferred(obligations, transaction_price, mid_year)
    deferred_end = calculate_deferred(obligations, transaction_price, contract_end)

    print(f"\n{'─' * 70}")
    print("DEFERRED REVENUE POSITION")
    print(f"{'─' * 70}")
    print(f"  As of {mid_year}: {deferred_mid}")
    print(f"  As of {contract_end}: {deferred_end}")


if __name__ == "__main__":
    main()
