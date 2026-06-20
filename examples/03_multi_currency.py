#!/usr/bin/env python3
"""Multi-currency invoicing with FX revaluation.

Demonstrates:

1. Create customers in EGP, USD, EUR
2. Set up FX rates for the currency pairs
3. Generate invoices in each customer's currency
4. Perform month-end revaluation
5. Show unrealized FX gains/losses
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from dinarledger.core.money import Money
from dinarledger.core.types import (
    BillingPeriod,
    Customer,
    Invoice,
    InvoiceStatus,
    LineItem,
    Plan,
)
from dinarledger.core.enums import InvoiceStatus as IS
from dinarledger.fx.rates import FXRate, convert, cross_rate
from dinarledger.fx.revaluation import revalue_ar, unrealized_gain
from dinarledger.subscriptions.lifecycle import subscribe
from dinarledger.billing.invoice_gen import generate_invoice


def main() -> None:
    # ── 1. Create a plan (base in USD) ───────────────────────────────────
    usd_plan = Plan(
        plan_id="pro-usd",
        name="Professional (USD)",
        base_price=Money(Decimal("99.00"), "USD"),
        billing_cycle="monthly",
    )

    # ── 2. Create customers in different currencies ──────────────────────
    customers = [
        Customer(customer_id="cust-us", name="American Corp", currency="USD"),
        Customer(customer_id="cust-eg", name="Cairo Solutions", currency="EGP"),
        Customer(customer_id="cust-eu", name="Berlin Tech GmbH", currency="EUR"),
    ]

    # ── 3. Set up FX rates ──────────────────────────────────────────────
    rate_date = date(2025, 1, 15)

    # USD/EGP rate: 1 USD = 48.50 EGP
    usd_egp = FXRate(base="USD", quote="EGP", rate=Decimal("48.50"), rate_date=rate_date)
    # USD/EUR rate: 1 USD = 0.92 EUR
    usd_eur = FXRate(base="USD", quote="EUR", rate=Decimal("0.92"), rate_date=rate_date)
    # EUR/EGP cross rate
    eur_egp_rate = cross_rate(usd_eur, usd_egp)
    print(f"FX Rates as of {rate_date}:")
    print(f"  USD/EGP: {usd_egp.rate}")
    print(f"  USD/EUR: {usd_eur.rate}")
    print(f"  EUR/EGP (cross): {eur_egp_rate}")

    # ── 4. Subscribe and generate invoices ───────────────────────────────
    period = BillingPeriod(start_date=date(2025, 1, 1), end_date=date(2025, 1, 31))
    invoices: list[Invoice] = []

    # USD customer — direct
    sub_us = subscribe("cust-us", usd_plan, date(2025, 1, 1))
    inv_us = generate_invoice(sub_us, period, {})
    if inv_us is not None:
        invoices.append(inv_us)
        print(f"\nUSD Invoice: {inv_us.invoice_id} — Total: {inv_us.total}")

    # EGP customer — convert plan price
    egp_price = convert(usd_plan.base_price, "EGP", usd_egp.rate)
    egp_plan = Plan(
        plan_id="pro-egp",
        name="Professional (EGP)",
        base_price=egp_price,
        billing_cycle="monthly",
    )
    sub_eg = subscribe("cust-eg", egp_plan, date(2025, 1, 1))
    inv_eg = generate_invoice(sub_eg, period, {})
    if inv_eg is not None:
        invoices.append(inv_eg)
        print(f"EGP Invoice: {inv_eg.invoice_id} — Total: {inv_eg.total}")

    # EUR customer — convert plan price
    eur_price = convert(usd_plan.base_price, "EUR", usd_eur.rate)
    eur_plan = Plan(
        plan_id="pro-eur",
        name="Professional (EUR)",
        base_price=eur_price,
        billing_cycle="monthly",
    )
    sub_eu = subscribe("cust-eu", eur_plan, date(2025, 1, 1))
    inv_eu = generate_invoice(sub_eu, period, {})
    if inv_eu is not None:
        invoices.append(inv_eu)
        print(f"EUR Invoice: {inv_eu.invoice_id} — Total: {inv_eu.total}")

    # ── 5. Month-end revaluation ─────────────────────────────────────────
    # Rates moved by month-end
    month_end = date(2025, 1, 31)
    new_usd_egp_rate = Decimal("49.20")  # EGP weakened
    new_usd_eur_rate = Decimal("0.94")   # EUR weakened

    print(f"\n{'─' * 60}")
    print(f"Month-end revaluation ({month_end.isoformat()})")
    print(f"  New USD/EGP: {new_usd_egp_rate}")
    print(f"  New USD/EUR: {new_usd_eur_rate}")
    print(f"{'─' * 60}")

    current_rates = {
        "EGP": new_usd_egp_rate,
        "EUR": new_usd_eur_rate,
    }

    # Store original rates for each invoice so revalue_ar can find them
    for inv in invoices:
        if inv._currency == "EGP":
            object.__setattr__(inv, "original_rate", usd_egp.rate)
        elif inv._currency == "EUR":
            object.__setattr__(inv, "original_rate", usd_eur.rate)
        else:
            object.__setattr__(inv, "original_rate", Decimal("1"))

    results = revalue_ar(invoices, current_rates, base_currency="USD")

    # Gains come back in the invoice's own currency; convert to USD for aggregation
    usd_gain = Money(Decimal("0"), "USD")
    usd_loss = Money(Decimal("0"), "USD")

    # Build a reverse-rate map: foreign -> USD
    to_usd_rates: dict[str, Decimal] = {}
    for ccy, rate in current_rates.items():
        # rate = foreign per 1 USD, so 1/rate = USD per 1 foreign
        to_usd_rates[ccy] = (Decimal("1") / rate).quantize(Decimal("0.000001"))

    for inv_id, gain in results:
        direction = "gain" if gain.amount >= Decimal("0") else "loss"
        abs_gain = Money(abs(gain.amount), gain.currency)
        # Convert to USD for totals
        usd_rate = to_usd_rates.get(gain.currency, Decimal("1"))
        usd_amount = Money(
            (abs_gain.amount * usd_rate).quantize(Decimal("0.01")),
            "USD",
        )
        if gain.amount >= Decimal("0"):
            usd_gain = usd_gain + usd_amount
        else:
            usd_loss = usd_loss + usd_amount
        print(f"  Invoice {inv_id[:8]}…: unrealized FX {direction} = {abs_gain} ({usd_amount} USD)")

    print(f"\n  Total unrealized FX gains:  {usd_gain}")
    print(f"  Total unrealized FX losses: {usd_loss}")

    # ── Summary ──────────────────────────────────────────────────────────
    print(f"\n{'=' * 60}")
    print("MULTI-CURRENCY SUMMARY")
    print(f"{'=' * 60}")
    for inv in invoices:
        print(f"  {inv.invoice_id[:8]}…  {inv._currency:>3}  Total: {inv.total}")
    print(f"  FX impact (net): {Money(usd_gain.amount - usd_loss.amount, 'USD')}")


if __name__ == "__main__":
    main()
