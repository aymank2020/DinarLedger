#!/usr/bin/env python3
"""Quickstart: subscribe a customer, generate an invoice, record payment.

Demonstrates the core billing workflow end-to-end:

1. Create a plan (KWD 50 / month)
2. Subscribe a customer
3. Generate an invoice for the billing period
4. Record a payment against the invoice
5. Print a summary
"""

from datetime import date
from decimal import Decimal

from dinarledger.core.money import Money
from dinarledger.core.types import (
    BillingPeriod,
    Customer,
    InvoiceStatus,
    LineItem,
    Payment,
    PaymentStatus,
    Plan,
    TaxRate,
)
from dinarledger.subscriptions.lifecycle import subscribe
from dinarledger.billing.invoice_gen import generate_invoice


def main() -> None:
    # ── 1. Create a plan ─────────────────────────────────────────────────
    plan = Plan(
        plan_id="plan-basic",
        name="Basic",
        base_price=Money(Decimal("50.00"), "KWD"),
        billing_cycle="monthly",
        setup_fee=Money(Decimal("25.00"), "KWD"),
        tax_code="KW_VAT",
    )
    print(f"Created plan: {plan}")

    # ── 2. Subscribe a customer ──────────────────────────────────────────
    customer = Customer(
        customer_id="cust-001",
        name="Acme Corp",
        currency="KWD",
    )
    subscription = subscribe(
        customer_id=customer.customer_id,
        plan=plan,
        start_date=date(2025, 1, 1),
    )
    print(f"Subscribed: {subscription}")

    # ── 3. Generate an invoice ───────────────────────────────────────────
    period = BillingPeriod(start_date=date(2025, 1, 1), end_date=date(2025, 1, 31))
    tax_rates = {
        "KW_VAT": TaxRate(
            code="KW_VAT",
            rate=Decimal("0.05"),
            description="Kuwait VAT",
        ),
    }
    invoice = generate_invoice(
        subscription,
        period,
        tax_rates,
        is_first_invoice=True,
    )
    if invoice is None:
        print("ERROR: could not generate invoice")
        return

    print(f"\nInvoice generated:")
    print(f"  ID:       {invoice.invoice_id}")
    print(f"  Customer: {invoice.customer_id}")
    print(f"  Period:   {invoice.period}")
    for li in invoice.line_items:
        print(f"  Line:     {li}")
    print(f"  Subtotal: {invoice.subtotal}")
    print(f"  Tax:      {invoice.total_tax}")
    print(f"  Total:    {invoice.total}")

    # ── 4. Record a payment ──────────────────────────────────────────────
    payment = Payment(
        payment_id="pay-001",
        invoice_id=invoice.invoice_id,
        amount=invoice.total,
        status=PaymentStatus.COMPLETED,
        paid_date=date(2025, 1, 15),
        reference="BANK-TRX-001",
    )
    print(f"\nPayment recorded: {payment}")

    # ── 5. Summary ───────────────────────────────────────────────────────
    print("\n" + "=" * 50)
    print("QUICKSTART SUMMARY")
    print("=" * 50)
    print(f"  Customer:    {customer.name} ({customer.customer_id})")
    print(f"  Plan:        {plan.name} @ {plan.base_price}")
    print(f"  Invoice:     {invoice.total}")
    print(f"  Payment:     {payment.amount} ({payment.status.value})")
    print(f"  Status:      PAID IN FULL")


if __name__ == "__main__":
    main()
