"""
dinarledger.core — Domain primitives, value objects, and error types.

This sub-package exposes the foundational building blocks used across the
billing, revenue, and payment modules.  Importing from ``dinarledger.core``
gives direct access to the most commonly used names without needing to
reach into individual sub-modules.
"""

from .errors import (
    AllocationError,
    BillingError,
    CreditLimitExceededError,
    CurrencyMismatchError,
    DinarLedgerError,
    ExemptionError,
    FXError,
    InvalidParameterError,
    InvoiceError,
    PaymentAllocationError,
    PaymentError,
    PlanNotFoundError,
    ProrationError,
    RateNotFoundError,
    RecognitionError,
    ReconciliationError,
    RevenueError,
    SubscriptionError,
    SubscriptionStateError,
    TaxError,
)
from .money import Money, sum_money, zero
from .period import (
    billing_periods,
    days_in_month,
    proration_fraction,
    stub_period,
)
from .types import (
    BillingPeriod,
    Customer,
    Invoice,
    InvoiceStatus,
    LineItem,
    Payment,
    PaymentStatus,
    Plan,
    Subscription,
    SubscriptionStatus,
    TaxRate,
)

__all__ = [
    # Errors
    "DinarLedgerError",
    "InvalidParameterError",
    "SubscriptionError",
    "SubscriptionStateError",
    "PlanNotFoundError",
    "BillingError",
    "InvoiceError",
    "CreditLimitExceededError",
    "ProrationError",
    "RevenueError",
    "RecognitionError",
    "AllocationError",
    "PaymentError",
    "PaymentAllocationError",
    "ReconciliationError",
    "FXError",
    "RateNotFoundError",
    "CurrencyMismatchError",
    "TaxError",
    "ExemptionError",
    # Money
    "Money",
    "sum_money",
    "zero",
    # Types
    "BillingPeriod",
    "Customer",
    "Invoice",
    "InvoiceStatus",
    "LineItem",
    "Payment",
    "PaymentStatus",
    "Plan",
    "Subscription",
    "SubscriptionStatus",
    "TaxRate",
    # Period
    "billing_periods",
    "days_in_month",
    "proration_fraction",
    "stub_period",
]
