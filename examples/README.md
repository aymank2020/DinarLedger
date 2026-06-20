# DinarLedger Examples

Self-contained scripts demonstrating DinarLedger's billing and revenue
recognition capabilities.  Each example can be run independently:

```bash
python examples/01_quickstart.py
```

## Index

| # | File | Description |
|---|------|-------------|
| 1 | `01_quickstart.py` | **Basic workflow** — create a plan, subscribe a customer, generate an invoice, record a payment. The simplest end-to-end scenario. |
| 2 | `02_saas_company.py` | **SaaS simulation** — model Year 1 of a SaaS company with 50 customers across three plans, handling upgrades, downgrades, and cancellations. Tracks MRR, churn rate, and total revenue. |
| 3 | `03_multi_currency.py` | **Multi-currency invoicing** — invoice customers in EGP, USD, and EUR; set up FX rates; perform month-end revaluation; report unrealized FX gains/losses. |
| 4 | `04_ifrs15_bundle.py` | **IFRS 15 SSP allocation** — create a multi-element arrangement (SaaS + onboarding + support), allocate the transaction price using proportional and residual methods, and generate a monthly revenue recognition schedule. |
| 5 | `05_payment_reconciliation.py` | **Bank reconciliation** — match recorded payments to bank statement entries using amount and date-proximity rules; report matched and unmatched items. |

## Prerequisites

All examples use only the DinarLedger package and the Python standard
library — no additional dependencies are required.

Install the package in development mode:

```bash
pip install -e .
```

## Running the Tests

The examples are also covered by a smoke-test suite:

```bash
pytest tests/examples/test_examples_run.py -v
```
