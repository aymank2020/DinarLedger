"""
Enumerations used throughout DinarLedger.

These enums encode the finite state spaces for invoices, subscriptions,
line-item types, and billing cycles.
"""

from enum import Enum, unique


@unique
class InvoiceStatus(Enum):
    """Lifecycle states of an invoice."""

    DRAFT = "draft"
    OPEN = "open"
    OVERDUE = "overdue"
    PAID = "paid"
    PARTIALLY_PAID = "partially_paid"
    VOIDED = "voided"


@unique
class SubscriptionStatus(Enum):
    """Lifecycle states of a subscription."""

    TRIAL = "trial"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


@unique
class LineItemType(Enum):
    """Classification of an invoice line item."""

    CHARGE = "charge"
    CREDIT = "credit"
    TAX = "tax"


@unique
class BillingCycle(Enum):
    """Billing cadence for a plan."""

    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"
