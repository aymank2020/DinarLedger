# Architecture Overview

DinarLedger is a multi-currency subscription billing and IFRS 15 revenue
recognition engine.  This document describes the module layout, data-flow
between components, design principles, and the dependency graph.

---

## Module Map (13 modules)

| # | Module | Path | Purpose |
|---|--------|------|---------|
| 1 | **core** | `dinarledger.core` | Money value type, domain entities (Plan, Subscription, Invoice, Payment, TaxRate, Customer), enums, error hierarchy, period/proration helpers |
| 2 | **subscriptions** | `dinarledger.subscriptions` | State machine (TRIAL → ACTIVE → CANCELLED/EXPIRED), reactivation window, plan changes, seat management |
| 3 | **billing** | `dinarledger.billing` | Invoice generation from subscriptions, line-item construction (recurring, seat overage, setup fee, tax), adjustments, voiding |
| 4 | **payments** | `dinarledger.payments` | Payment allocation across invoices (oldest-first / highest-first), bank reconciliation with tolerance matching |
| 5 | **revenue** | `dinarledger.revenue` | IFRS 15 Step 4–5: performance obligations, SSP allocation (proportional & residual), ratable/point-in-time recognition, deferred revenue schedules |
| 6 | **fx** | `dinarledger.fx` | FX rate quotes, currency conversion, cross-rate derivation, month-end AR revaluation, unrealized gain/loss |
| 7 | **tax** | `dinarledger.tax` | Per-item tax computation (round-per-item), customer/jurisdiction exemptions, tax summaries |
| 8 | **customers** | `dinarledger.customers` | Credit-limit enforcement, AR ledger (per-customer running balance) |
| 9 | **plans** | `dinarledger.plans` | Proration fractions, net upgrade/downgrade credit calculations |
| 10 | **reports** | `dinarledger.reports` | AR aging buckets, MRR breakdown (new / expansion / contraction / churn), deferred-revenue waterfall |
| 11 | **cli** | `dinarledger.cli` | Argparse-based CLI with subcommands: customer, plan, subscription, invoice, payment, revenue, fx, report. Output in table / JSON / CSV |
| 12 | **storage** | `dinarledger.storage` | Abstract `Repository[T]`, MemoryRepository, JsonRepository, SqliteRepository, Unit of Work, serializers, migrations |
| 13 | **jobs** | *(planned)* | Scheduled tasks: invoice generation, dunning, FX rate refresh, period-close |

---

## Data Flow Diagram

```
                    ┌──────────┐
                    │   CLI    │  dinarledger <command> <subcommand>
                    └────┬─────┘
                         │  dispatches
            ┌────────────┼────────────────┐
            v            v                v
      ┌──────────┐ ┌──────────┐   ┌───────────┐
      │customers │ │   fx     │   │  reports   │
      │  credit  │ │  rates   │   │ aging/mrr  │
      └────┬─────┘ └────┬─────┘   └─────┬─────┘
           │            │               │
           v            v               │
      ┌─────────────────────────────┐   │
      │      subscriptions          │   │
      │  subscribe / cancel / react │   │
      └────────────┬────────────────┘   │
                   │                     │
                   v                     │
      ┌─────────────────────────┐       │
      │        billing          │       │
      │  generate_invoice()     │───────┘
      └────────────┬────────────┘
                   │
         ┌─────────┼──────────┐
         v         v          v
   ┌──────────┐ ┌───────┐ ┌─────────┐
   │   tax    │ │   fx  │ │ payments│
   │calc+exemp│ │convert│ │ allocate│
   └──────────┘ └───────┘ │reconcile│
                         └────┬────┘
                              │
                              v
                    ┌──────────────────┐
                    │     revenue      │
                    │ IFRS 15 recogn.  │
                    │ deferred sched.  │
                    └────────┬─────────┘
                             │
                             v
                    ┌──────────────────┐
                    │     storage      │
                    │ repo / UoW / migr│
                    └──────────────────┘
```

---

## Design Principles

### 1. Immutability

All domain types (`Money`, `Plan`, `Subscription`, `Invoice`, `LineItem`,
`Payment`, `TaxRate`, `Customer`, `BillingPeriod`) are **frozen dataclasses**.
Mutations return a new instance via `dataclasses.replace()`:

```python
updated = replace(subscription, status=SubscriptionStatus.ACTIVE)
```

This eliminates an entire class of aliasing bugs and makes the code safe for
concurrent reads.

### 2. Decimal Precision

Every monetary amount is a `decimal.Decimal`.  `float` is never used for
money.  The `Money` class rejects `float` in its constructor and provides
`Money.from_float()` for the rare cases where a float source is unavoidable.

Rounding defaults to **banker's rounding** (`ROUND_HALF_EVEN`) in the `Money`
class, matching the convention used by most financial jurisdictions.  Tax
and proration calculations use `ROUND_HALF_UP` where required by regulation.

### 3. Currency Safety

Adding or comparing `Money` values with different currencies raises
`CurrencyMismatchError` rather than silently converting.  All FX conversions
are explicit: the caller must supply the `FXRate` and use `fx.convert()`.

### 4. Validation at Construction

Every frozen dataclass validates invariants in `__post_init__`.  An invalid
`BillingPeriod`, `Plan`, or `Subscription` simply cannot exist — you get an
`InvalidParameterError` at the point of creation, not deep inside a
calculation.

### 5. Structured Errors

The exception hierarchy under `DinarLedgerError` mirrors the domain:

```
DinarLedgerError
  ├── InvalidParameterError
  ├── SubscriptionError  →  SubscriptionStateError, PlanNotFoundError
  ├── BillingError       →  InvoiceError, CreditLimitExceededError, ProrationError
  ├── RevenueError       →  RecognitionError, AllocationError
  ├── PaymentError       →  PaymentAllocationError, ReconciliationError
  ├── FXError            →  RateNotFoundError, CurrencyMismatchError
  └── TaxError           →  ExemptionError
```

Every exception carries a `context` dict for programmatic inspection.

---

## Module Dependency Graph (ASCII)

```
                          core
                       (money/types/enums/errors/period)
                            │
          ┌─────────┬───────┼────────┬──────────┐
          v         v       v        v          v
       plans    subscriptions  billing    fx      tax
          │         │          │         │        │
          │         │          │         │        │
          └────┬────┘          │    ┌────┘        │
               v               v    v             v
          customers        payments  revaluation  calculator
               │               │
               └───────┬───────┘
                       v
                    revenue
              (recognition/allocation/deferred)
                       │
                       v
                    reports
              (aging/mrr/deferred_schedule)
                       │
                       v
                    storage
           (memory/json/sqlite/uow/migrations)
                       │
                       v
                      cli
          (commands/formatters/store/main)
```

**Key rules:**

- `core` has **no** inward dependencies — it defines the vocabulary.
- `storage` depends on `core` types for serialization but not on domain logic.
- `cli` is the thinnest layer; it delegates to domain modules and formats
  output.
- Circular dependencies are avoided by using deferred imports where needed
  (e.g. `lifecycle.py` imports from `plans.proration`).

---

## Thread Safety

- `MemoryRepository` uses a `threading.Lock` for all reads and writes.
- `SqliteRepository` delegates to SQLite's built-in transaction isolation.
- Domain objects (frozen dataclasses) are inherently thread-safe for reads.
- The `UnitOfWork` context manager provides atomic multi-repository
  operations with rollback on exception.
