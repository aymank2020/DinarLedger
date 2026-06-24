# IFRS 15 / ASC 606 Implementation

DinarLedger implements the **five-step model** of IFRS 15 *Revenue from
Contracts with Customers* (and its US GAAP twin, ASC 606).  This document
explains how each step maps to code, the supported recognition patterns,
and known limitations.

---

## The Five-Step Model

| Step | IFRS 15 Reference | DinarLedger Module | Key Function / Class |
|------|-------------------|--------------------|-----------------------|
| 1. Identify the contract | 9–11 | `subscriptions.lifecycle` | `subscribe()` creates the contract |
| 2. Identify performance obligations | 22–30 | `revenue.recognition` | `PerformanceObligation` dataclass |
| 3. Determine the transaction price | 47–72 | `billing.invoice_gen` | `generate_invoice()` → `Invoice.total` |
| 4. Allocate the transaction price | 73–86 | `revenue.allocation` | `allocate_transaction_price()`, `residual_allocation()` |
| 5. Recognise revenue | 31–45 | `revenue.recognition` | `recognize_revenue()`, `calculate_deferred()` |

---

## Step 1 — Identify the Contract

A contract is represented by a `Subscription` tying a `Customer` to a `Plan`.
The contract is considered active when `subscription.is_active` is `True`
(status `ACTIVE` or `TRIAL`).  Cancelled and expired subscriptions are
excluded from billing and recognition.

The lifecycle state machine enforces valid transitions:

```
TRIAL ──activate()──→ ACTIVE ──cancel(immediate=True)──→ CANCELLED
                       ACTIVE ──cancel(immediate=False)──→ ACTIVE *
                                                       (cancelled_at set)

CANCELLED ──reactivate()──→ ACTIVE   (within 30-day window)
```

---

## Step 2 — Identify Performance Obligations

A `PerformanceObligation` is a distinct promise within a contract.  Each
obligation has:

- **`obligation_id`** — unique identifier
- **`description`** — human-readable label
- **`standalone_price`** — the standalone selling price (SSP) as `Money`
- **`satisfied_over_time`** — `True` for over-time; `False` for point-in-time
- **`start_date`** / **`end_date`** — the performance window

### Over-Time vs Point-in-Time

| Pattern | `satisfied_over_time` | Recognition |
|---------|----------------------|-------------|
| Subscription access (monthly SaaS) | `True` | Ratable over the obligation period |
| One-time setup / delivery | `False` | Full amount when `end_date` falls in the period |

A subscription with a setup fee typically has **two** obligations:
1. Over-time: ongoing service access
2. Point-in-time: setup / onboarding delivered at contract start

---

## Step 3 — Determine the Transaction Price

The transaction price is the `Invoice.total` (subtotal + tax).  For
multi-element arrangements this is the **total** that must be allocated
across all performance obligations.

DinarLedger does not currently model variable consideration estimates
(step 3 constraint) — the transaction price is taken as the invoiced amount.

---

## Step 4 — Allocate the Transaction Price

### Proportional Allocation (`allocate_transaction_price`)

Each obligation receives:

```
allocated = transaction_price × (obligation_ssp / total_ssp)
```

Rounded to 2 decimal places with `ROUND_HALF_UP`.  The last bucket absorbs
the rounding remainder so the total reconciles.

**Example:** Transaction price $1,000 with two obligations (SSP $600 and
$400):

| Obligation | SSP | Ratio | Allocated |
|-----------|-----|-------|-----------|
| Service   | $600 | 60%  | $600.00   |
| Setup     | $400 | 40%  | $400.00   |

### Residual Allocation (`residual_allocation`)

When some obligations have **no observable SSP** (zero `standalone_price`),
IFRS 15 permits the residual approach (15.78–15.80):

1. Obligations **with** observable SSP receive their full SSP.
2. The **residual** (transaction price − sum of known SSPs) is split equally
   among uncertain obligations.
3. If the residual is negative (discount exceeds the uncertain bucket),
   fall back to proportional allocation for known obligations and assign
   zero to uncertain ones.

---

## Step 5 — Recognise Revenue

### Over-Time Recognition

For `satisfied_over_time=True` obligations, revenue is recognised ratably:

```
monthly_amount = allocated_price / total_months
```

Stub months (partial first/last month) use daily proration:

```
stub_amount = monthly_amount × (days_active / days_in_month)
```

All amounts are quantised to 2 decimal places with `ROUND_HALF_UP`.

### Point-in-Time Recognition

For `satisfied_over_time=False` obligations, the full allocated amount is
recognised in the period that contains `end_date`:

```python
if period.start_date <= obl.end_date <= period.end_date:
    recognise full allocated amount
```

### `recognize_revenue()` Return Value

Returns a list of `(obligation_id, Money)` tuples — one per obligation —
showing the amount recognised in the given `BillingPeriod`.

---

## Deferred Revenue

`calculate_deferred()` computes the remaining deferred revenue as of a
reporting date:

```
deferred = sum(allocated_price − cumulative_recognised) for each obligation
```

- Over-time obligations with `end_date = None` (perpetual) are fully deferred.
- Obligations not yet started (`as_of < start_date`) are fully deferred.
- Obligations fully satisfied (`as_of >= end_date`) contribute zero.
- Negative balances (rounding artefacts) are clamped to zero.

This supports the standard **deferred revenue roll-forward**:

```
Opening deferred
  + New billings
  − Revenue recognised
  = Closing deferred
```

---

## Edge Cases and Limitations

| Area | Limitation | Workaround |
|------|-----------|------------|
| Variable consideration | Not modelled — transaction price is fixed | Pre-compute estimates externally |
| Significant financing component | Not separated | Include in transaction price |
| Contract modifications | Treated as new obligations | Create a new `PerformanceObligation` list |
| Multi-currency obligations | All obligations must share one currency | Convert before calling `recognize_revenue` |
| Rounding residual | Last obligation absorbs rounding; small drift possible | Reconcile `sum(allocated) == transaction_price` |
| Perpetual obligations | `end_date=None` → always fully deferred | Set a far-future `end_date` for recognition |
| Right-of-return / Refunds | Not modelled | Reduce transaction price before allocation |
| Licence-based recognition | Only over-time / point-in-time patterns | Custom logic needed for "right-to-access" vs "right-to-use" |

---

## Quick Reference: Code → IFRS 15 Mapping

```python
from dinarledger.revenue.recognition import (
    PerformanceObligation,     # Step 2
    recognize_revenue,         # Step 5
    calculate_deferred,        # Step 5 (balance)
)
from dinarledger.revenue.allocation import (
    allocate_transaction_price,  # Step 4 proportional
    residual_allocation,         # Step 4 residual
)
from dinarledger.revenue.deferred import (
    deferred_roll_forward,       # Period-close roll-forward
)
```
