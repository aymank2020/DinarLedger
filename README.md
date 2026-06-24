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

## CLI Usage

DinarLedger ships a CLI for common operations:

```bash
# List all customers
dinarledger customer list

# Create a plan
dinarledger plan create --id pro-monthly --name "Pro Monthly" --price 99.00 --currency USD --cycle monthly

# Subscribe a customer
dinarledger subscription create --customer C-001 --plan pro-monthly --start 2026-01-01

# Generate an invoice
dinarledger invoice generate --subscription sub-1 --period-start 2026-01-01 --period-end 2026-01-31

# Record a payment
dinarledger payment record --invoice INV-001 --amount 99.00 --currency USD

# Recognise revenue
dinarledger revenue recognize --period-start 2026-01-01 --period-end 2026-01-31

# FX rate management
dinarledger fx set-rate --base KWD --quote USD --rate 3.2600 --date 2026-01-31

# Reports
dinarledger report aging --as-of 2026-01-31
dinarledger report mrr --month 2026-01-01
dinarledger report deferred --as-of 2026-01-31
```

Output format can be controlled with `--format` (`table`, `json`, or `csv`) or
the `OUTPUT_FORMAT` environment variable.

---

## Storage / Persistence

DinarLedger supports three storage backends:

| Backend | Best For | Persistence | Transactions |
|---------|----------|-------------|-------------|
| **MemoryRepository** | Testing, prototyping | In-process only | Simulated (snapshot) |
| **JsonRepository** | Dev, single-instance | JSON files | Simulated (snapshot) |
| **SqliteRepository** | Production | SQLite database | Real ACID |

```python
from dinarledger.storage.memory import MemoryRepository
from dinarledger.storage.json_store import JsonRepository
from dinarledger.storage.sqlite_store import SqliteRepository
from dinarledger.core.types import Plan

# In-memory (testing)
repo = MemoryRepository(Plan)

# JSON file (development)
repo = JsonRepository(Plan, path="data/plans.json")

# SQLite (production)
repo = SqliteRepository(Plan, db_path="dinarledger.db")
```

For atomic multi-repository operations, use the Unit of Work pattern:

```python
from dinarledger.storage.unit_of_work import UnitOfWork

with UnitOfWork(customer_repo, invoice_repo) as uow:
    customer_repo.add(customer)
    invoice_repo.add(invoice)
    # Auto-commits on success, rolls back on exception
```

See [docs/persistence.md](docs/persistence.md) for the full guide.

---

## Job Scheduling

DinarLedger is designed to integrate with external schedulers (cron, Celery,
APScheduler) for periodic tasks:

| Job | Frequency | Description |
|-----|-----------|-------------|
| Invoice generation | Monthly / per cycle | Generate invoices for active subscriptions |
| Dunning | Daily | Mark overdue invoices, send reminders |
| FX rate refresh | Daily | Pull latest rates from provider |
| Revenue recognition | Monthly | Run `recognize_revenue()` for the closed period |
| Month-end revaluation | Monthly | Revalue foreign-currency AR at closing rates |
| AR aging snapshot | Daily | Record aging buckets for trend analysis |

---

## Examples

The `examples/` directory contains end-to-end scenarios:

- **Basic billing cycle** — subscribe → invoice → pay → recognise revenue
- **Mid-cycle upgrade** — plan change with proration credit
- **Multi-currency** — FX conversion, cross rates, month-end revaluation
- **IFRS 15 allocation** — proportional and residual SSP allocation

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
├── reports/        # AR Aging, MRR, Deferred waterfall
├── storage/        # Memory/JSON/SQLite repos, Unit of Work, Migrations
├── cli/            # CLI commands and formatters
└── utils/          # Date helpers, Decimal helpers, Slug generation

tests/              # 60+ tests with pytest + hypothesis
docs/               # Architecture, IFRS 15, FX, Persistence guides
```

---

## Development Setup

```bash
# Clone and set up environment
git clone https://github.com/aymank2020/DinarLedger.git
cd DinarLedger
python -m venv .venv
source .venv/bin/activate

# Install with dev dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Run tests
pytest --cov=dinarledger --cov-report=term-missing

# Run property-based tests
pytest tests/properties/ -v

# Type checking
mypy src/dinarledger

# Linting
ruff check src/dinarledger
```

---

## Documentation

| Document | Description |
|----------|-------------|
| [docs/architecture.md](docs/architecture.md) | Module overview, data flow, dependency graph, design principles |
| [docs/ifrs15.md](docs/ifrs15.md) | IFRS 15 five-step model mapping, SSP allocation, recognition mechanics |
| [docs/fx.md](docs/fx.md) | FX rate conventions, conversion direction, cross rates, revaluation |
| [docs/persistence.md](docs/persistence.md) | Repository backends, migrations, Unit of Work, decision matrix |

---

## Running Tests

```bash
# Full test suite with coverage
pytest --cov=dinarledger --cov-report=term-missing

# Unit tests only
pytest tests/ -v

# Property-based tests
pytest tests/properties/ -v

# Slow / integration tests
pytest -m integration

# With hypothesis max examples
pytest tests/properties/ --hypothesis-max-examples=200
```

---

## License

MIT — see [LICENSE](LICENSE).

## Author

Ayman Mohamed — ayman.dev@proton.me
