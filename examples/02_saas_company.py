#!/usr/bin/env python3
"""Year 1 of a SaaS company simulation.

Creates three plans (Starter, Professional, Enterprise) and simulates 50
customers over 12 months, including upgrades, downgrades, and cancellations.
Tracks MRR, churn rate, and total revenue, printing a monthly summary.
"""

from __future__ import annotations

import random
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from typing import List

from dinarledger.core.enums import SubscriptionStatus
from dinarledger.core.money import Money, zero
from dinarledger.core.types import (
    BillingPeriod,
    Customer,
    Invoice,
    InvoiceStatus,
    LineItem,
    Payment,
    PaymentStatus,
    Plan,
    TaxRate,
)
from dinarledger.subscriptions.lifecycle import (
    cancel_subscription,
    change_plan,
    subscribe,
)
from dinarledger.billing.invoice_gen import generate_invoice
from dinarledger.reports.mrr import calculate_mrr

# ── Configuration ────────────────────────────────────────────────────────────

SEED = 42
NUM_CUSTOMERS = 50
MONTHS = 12
START_DATE = date(2025, 1, 1)

# ── Plans ────────────────────────────────────────────────────────────────────

PLANS = {
    "starter": Plan(
        plan_id="starter",
        name="Starter",
        base_price=Money(Decimal("29.00"), "USD"),
        billing_cycle="monthly",
    ),
    "professional": Plan(
        plan_id="professional",
        name="Professional",
        base_price=Money(Decimal("79.00"), "USD"),
        billing_cycle="monthly",
    ),
    "enterprise": Plan(
        plan_id="enterprise",
        name="Enterprise",
        base_price=Money(Decimal("199.00"), "USD"),
        billing_cycle="monthly",
    ),
}

TAX_RATE = TaxRate(code="US_SALES", rate=Decimal("0.00"), description="No tax (sim)", is_exempt=True)
TAX_RATES = {"US_SALES": TAX_RATE}

# ── Helpers ──────────────────────────────────────────────────────────────────

def _month_end(year: int, month: int) -> date:
    if month == 12:
        return date(year + 1, 1, 1) - timedelta(days=1)
    return date(year, month + 1, 1) - timedelta(days=1)


def _pick_plan(rng: random.Random) -> str:
    r = rng.random()
    if r < 0.50:
        return "starter"
    if r < 0.85:
        return "professional"
    return "enterprise"


# ── Simulation ───────────────────────────────────────────────────────────────

def run_simulation() -> None:
    rng = random.Random(SEED)

    # Create customers
    customers: list[Customer] = [
        Customer(customer_id=f"cust-{i:03d}", name=f"Customer {i}", currency="USD")
        for i in range(1, NUM_CUSTOMERS + 1)
    ]

    # Active subscriptions indexed by customer_id
    subs: dict[str, tuple] = {}  # customer_id -> Subscription
    all_subs: list = []  # every subscription ever created

    total_revenue = zero("USD")
    total_churned = 0

    print("=" * 80)
    print("DinarLedger SaaS Company — Year 1 Simulation")
    print("=" * 80)

    for month in range(1, MONTHS + 1):
        month_start = date(START_DATE.year, month, 1)
        month_end = _month_end(START_DATE.year, month)
        period = BillingPeriod(start_date=month_start, end_date=month_end)

        # ── New subscriptions ─────────────────────────────────────────
        # Month 1: all 50 sign up; later months: a few new customers
        new_count = NUM_CUSTOMERS if month == 1 else rng.randint(0, 4)
        available = [c for c in customers if c.customer_id not in subs]
        for c in available[:new_count]:
            plan_key = _pick_plan(rng)
            sub = subscribe(c.customer_id, PLANS[plan_key], month_start)
            subs[c.customer_id] = sub
            all_subs.append(sub)

        # ── Plan changes (upgrade / downgrade) ────────────────────────
        plan_changes = 0
        active_ids = list(subs.keys())
        for cid in active_ids:
            if rng.random() < 0.05:  # 5% chance per month
                sub = subs[cid]
                if sub.status != SubscriptionStatus.ACTIVE:
                    continue
                current_plan = sub.plan.plan_id
                plan_keys = list(PLANS.keys())
                plan_keys.remove(current_plan)
                new_plan_key = rng.choice(plan_keys)
                try:
                    sub, net = change_plan(sub, PLANS[new_plan_key], month_start)
                    subs[cid] = sub
                    plan_changes += 1
                except Exception:
                    pass  # skip invalid changes

        # ── Cancellations ─────────────────────────────────────────────
        churned_this_month = 0
        if month >= 3:  # no churn in first two months
            for cid in list(subs.keys()):
                if rng.random() < 0.04:  # 4% monthly churn
                    sub = subs[cid]
                    if sub.status != SubscriptionStatus.ACTIVE:
                        continue
                    try:
                        sub = cancel_subscription(sub, month_start, immediate=True)
                        subs[cid] = sub
                        churned_this_month += 1
                        total_churned += 1
                    except Exception:
                        pass

        # ── Generate invoices for active subs ─────────────────────────
        month_revenue = zero("USD")
        invoices_generated = 0
        for cid, sub in subs.items():
            if sub.status != SubscriptionStatus.ACTIVE:
                continue
            inv = generate_invoice(sub, period, TAX_RATES)
            if inv is not None:
                month_revenue = month_revenue + inv.total
                invoices_generated += 1

        total_revenue = total_revenue + month_revenue

        # ── MRR calculation ───────────────────────────────────────────
        mrr = calculate_mrr(all_subs, PLANS, month_start)
        active_count = sum(
            1 for s in subs.values() if s.status == SubscriptionStatus.ACTIVE
        )
        churn_rate = (churned_this_month / max(active_count + churned_this_month, 1)) * 100

        # ── Print monthly summary ─────────────────────────────────────
        print(f"\n── Month {month:2d} ({month_start.isoformat()}) "
              f"{'─' * 45}")
        print(f"  Active subs:     {active_count}")
        print(f"  New subs:        {new_count}")
        print(f"  Plan changes:    {plan_changes}")
        print(f"  Churned:         {churned_this_month}")
        print(f"  Churn rate:      {churn_rate:.1f}%")
        print(f"  Invoices:        {invoices_generated}")
        print(f"  Month revenue:   {month_revenue}")
        print(f"  MRR (total):     {mrr.total_mrr}")
        print(f"  New MRR:         {mrr.new_mrr}")
        print(f"  Churn MRR:       {mrr.churn_mrr}")

    # ── Annual Summary ─────────────────────────────────────────────────
    final_active = sum(
        1 for s in subs.values() if s.status == SubscriptionStatus.ACTIVE
    )
    print("\n" + "=" * 80)
    print("YEAR 1 SUMMARY")
    print("=" * 80)
    print(f"  Total customers:     {NUM_CUSTOMERS}")
    print(f"  Active at year-end:  {final_active}")
    print(f"  Total churned:       {total_churned}")
    print(f"  Total revenue:       {total_revenue}")
    print(f"  Avg monthly revenue: {Money(total_revenue.amount / 12, 'USD')}")


if __name__ == "__main__":
    run_simulation()
