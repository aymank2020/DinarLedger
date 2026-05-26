# DinarLedger

**Multi-currency subscription billing & IFRS 15 revenue recognition engine.**

A Python library for managing subscription lifecycles, multi-currency invoicing, revenue recognition under IFRS 15 / ASC 606, FX-aware payment reconciliation, and AR reporting.

---

## Features

- **Subscription Lifecycle** — Trial, Active, Cancelled (immediate or end-of-period), Expired states with reactivation window
- **Billing / Invoicing** — Automatic invoice generation with per-seat pricing, setup fees, tax lines, and proration
- **Multi-Currency** — Full FX rate management, currency conversion, cross-rate derivation, and unrealized gain/loss revaluation
- **IFRS 15 Revenue Recognition** — Performance obligations, standalone selling price allocation (proportional & residual), ratable and point-in-time recognition, deferred revenue schedules
- **Payment Management** — Configurable allocation strategies (oldest-first, highest-first), bank reconciliation with tolerance matching
- **Tax Engine** — Per-item tax computation, customer-level and jurisdiction-based exemptions
- **AR Reporting** — Aging reports, MRR breakdowns, deferred revenue waterfall
- **Decimal Precision** — All monetary operations use `decimal.Decimal` with banker's rounding

---

## Installation

```bash
pip install dinarledger
```

For development:

```bash
git clone https://github.com/aymank2020/DinarLedger.git
cd DinarLedger
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\Activate.ps1 on Windows
pip install -e ".[dev]"
```

---

## Quick Start

```python
from datetime import date
from decimal import Decimal
from dinarledger.core.money import Money
from dinarledger.core.types import Plan, Subscription, InvoiceStatus, SubscriptionStatus
from dinarledger.subscriptions.lifecycle import subscribe, cancel_subscription
from dinarledger.billing.invoice_gen import generate_invoice

# Create a plan
plan = Plan(
    plan_id="pro-monthly",
    name="Pro Monthly",
    base_price=Money(Decimal("99.00"), "USD"),
    billing_cycle="monthly",
)

# Subscribe a customer
sub = subscribe(customer_id="C-001", plan=plan, start_date=date(2026, 1, 1))
print(sub)  # Subscription(sub-1: C-001 -> pro-monthly, active, open-ended)

# Generate an invoice
from dinarledger.core.types import BillingPeriod
invoice = generate_invoice(
    subscription=sub,
    period=BillingPeriod(date(2026, 1, 1), date(2026, 1, 31)),
    tax_rates={},
)
print(f"Invoice total: {invoice.total}")  # Invoice total: 99.00 USD
```

---

## Project Structure

```
src/dinarledger/
├── core/           # Money, Types, Enums, Errors, Period utilities
├── customers/      # Credit limits, AR Ledger
├── plans/          # Proration, Upgrade credits
├── subscriptions/  # Lifecycle state machine, Seats
├── billing/        # Invoice generation
├── revenue/        # IFRS 15 Recognition, Allocation, Deferred schedules
├── payments/       # Payment allocation, Bank reconciliation
├── fx/             # FX rates, Currency conversion, Revaluation
├── tax/            # Tax calculation, Exemptions
└── reports/        # AR Aging, MRR, Deferred waterfall

tests/              # 60+ tests with pytest
```

---

## Running Tests

```bash
pytest --cov=dinarledger --cov-report=term-missing
```

---

## License

MIT — see [LICENSE](LICENSE).

## Author

Ayman Mohamed — ayman.dev@proton.me
