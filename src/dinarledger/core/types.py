"""
dinarledger.core.types — core domain value objects and entities.

Defines the primary domain types: plans, subscriptions, invoices,
payments, customers, and tax rates. Every type is a frozen dataclass
with ``__post_init__`` validation so that invalid state cannot be
constructed.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import List

from .enums import InvoiceStatus, SubscriptionStatus
from .errors import InvalidParameterError
from .money import Money, sum_money as _sum_money, zero as _zero


# ---------------------------------------------------------------------------
# BillingPeriod
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BillingPeriod:
    """A contiguous date range used for billing calculations.

    The range is inclusive on both ends. Raises
    :class:`InvalidParameterError` when *start_date* is on or after
    *end_date*.
    """

    start_date: date
    end_date: date

    def __post_init__(self) -> None:
        if self.start_date >= self.end_date:
            raise InvalidParameterError(
                "start_date",
                message=(
                    f"BillingPeriod start_date ({self.start_date}) must be "
                    f"strictly before end_date ({self.end_date})"
                ),
            )

    @property
    def days(self) -> int:
        """Number of days in the period (inclusive of both endpoints)."""
        return (self.end_date - self.start_date).days + 1

    def __str__(self) -> str:
        return f"{self.start_date.isoformat()}..{self.end_date.isoformat()}"


# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------

_ALLOWED_BILLING_CYCLES = ("monthly", "quarterly", "annual")


@dataclass(frozen=True)
class Plan:
    """A billable plan that customers can subscribe to."""

    plan_id: str
    name: str
    base_price: Money
    billing_cycle: str
    setup_fee: Money | None = None
    trial_days: int = 0
    tax_code: str = ""
    seats_included: int = 1

    def __post_init__(self) -> None:
        if self.billing_cycle not in _ALLOWED_BILLING_CYCLES:
            raise InvalidParameterError(
                "billing_cycle",
                message=(
                    f"billing_cycle must be one of {_ALLOWED_BILLING_CYCLES}, "
                    f"got '{self.billing_cycle}'"
                ),
            )
        if self.trial_days < 0:
            raise InvalidParameterError(
                "trial_days",
                message=f"trial_days must be >= 0, got {self.trial_days}",
            )

    def __str__(self) -> str:
        return f"Plan({self.plan_id}: {self.name} @ {self.base_price}/{self.billing_cycle})"


# ---------------------------------------------------------------------------
# Subscription
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Subscription:
    """A customer's subscription to a plan."""

    sub_id: str
    customer_id: str
    plan: Plan
    status: SubscriptionStatus
    start_date: date
    end_date: date | None = None
    seat_count: int = 1
    cancelled_at: date | None = None
    current_period_start: date | None = None
    current_period_end: date | None = None
    trial_ends_at: date | None = None

    def __post_init__(self) -> None:
        if self.seat_count < 1:
            raise InvalidParameterError(
                "seat_count",
                message=f"seat_count must be >= 1, got {self.seat_count}",
            )

    @property
    def is_active(self) -> bool:
        """``True`` when the subscription is in an active billable state."""
        return self.status in (SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL)

    @property
    def effective_price(self) -> Money:
        """Total price accounting for seat count."""
        return self.plan.base_price * self.seat_count

    def __str__(self) -> str:
        end = self.end_date.isoformat() if self.end_date else "open-ended"
        return (
            f"Subscription({self.sub_id}: {self.customer_id} -> "
            f"{self.plan.plan_id}, {self.status.value}, {end})"
        )


# ---------------------------------------------------------------------------
# Invoice
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LineItem:
    """A single line on an invoice.

    Tax lines (``is_tax=True``) carry a tax charge and are excluded from
    further tax computation.
    """

    description: str
    amount: Money
    tax_code: str = ""
    is_tax: bool = False
    quantity: Decimal = Decimal("1")
    item_type: str = "charge"

    def __str__(self) -> str:
        tag = " [TAX]" if self.is_tax else ""
        return f"{self.description}{tag}: {self.amount}"


@dataclass(frozen=True)
class Invoice:
    """An invoice aggregating line items for a customer."""

    invoice_id: str
    customer_id: str
    issue_date: date
    due_date: date
    line_items: List[LineItem] = field(default_factory=list)
    status: InvoiceStatus = InvoiceStatus.DRAFT
    subscription_id: str = ""
    period: BillingPeriod | None = None

    def __post_init__(self) -> None:
        if self.due_date < self.issue_date:
            raise InvalidParameterError(
                "due_date",
                message=(
                    f"due_date ({self.due_date}) must be >= issue_date "
                    f"({self.issue_date})"
                ),
            )

    # -- Computed properties --------------------------------------------------

    @property
    def subtotal(self) -> Money:
        """Sum of non-tax line-item amounts (pre-tax)."""
        non_tax = [li.amount for li in self.line_items if not li.is_tax]
        if not non_tax:
            for li in self.line_items:
                return _zero(li.amount.currency)
            return _zero("USD")
        return _sum_money(non_tax)

    @property
    def total_tax(self) -> Money:
        """Sum of tax line-item amounts."""
        tax_items = [li.amount for li in self.line_items if li.is_tax]
        if not tax_items:
            return _zero(self._currency)
        return _sum_money(tax_items)

    @property
    def total(self) -> Money:
        """Grand total — subtotal + tax."""
        return self.subtotal + self.total_tax

    @property
    def _currency(self) -> str:
        """Currency inferred from the first line item, or ``"USD"``."""
        for li in self.line_items:
            return li.amount.currency
        return "USD"

    def __str__(self) -> str:
        return (
            f"Invoice({self.invoice_id}: {self.customer_id}, "
            f"{self.status.value}, total={self.total})"
        )


# ---------------------------------------------------------------------------
# Payment
# ---------------------------------------------------------------------------

class PaymentStatus(enum.Enum):
    """Possible states of a payment."""

    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


@dataclass(frozen=True)
class Payment:
    """A payment applied against an invoice."""

    payment_id: str
    invoice_id: str
    amount: Money
    status: PaymentStatus
    paid_date: date | None = None
    reference: str = ""

    def __str__(self) -> str:
        return (
            f"Payment({self.payment_id}: invoice={self.invoice_id}, "
            f"{self.amount}, {self.status.value})"
        )


# ---------------------------------------------------------------------------
# TaxRate
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TaxRate:
    """A tax rate definition.

    ``is_exempt=True`` forces ``compute_tax`` to return zero.
    """

    code: str
    rate: Decimal
    description: str
    is_exempt: bool = False

    def compute_tax(self, amount: Money) -> Money:
        """Compute tax on *amount* using this rate.

        Returns the tax amount quantised to two decimal places (banker's
        rounding) or zero when the rate is marked exempt.
        """
        if self.is_exempt:
            return _zero(amount.currency)
        return (amount * self.rate).quantize()

    def __str__(self) -> str:
        pct = self.rate * Decimal("100")
        exempt = " (exempt)" if self.is_exempt else ""
        return f"TaxRate({self.code}: {pct}%{exempt} — {self.description})"


# ---------------------------------------------------------------------------
# Customer
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Customer:
    """A customer (account) in the billing system."""

    customer_id: str
    name: str
    currency: str
    credit_limit: Money | None = None
    tax_exempt: bool = False
    tax_jurisdiction: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "currency", self.currency.upper())
        if self.credit_limit is not None and self.credit_limit.currency != self.currency:
            raise InvalidParameterError(
                "credit_limit",
                message=(
                    f"credit_limit currency ({self.credit_limit.currency}) does not "
                    f"match customer currency ({self.currency})"
                ),
            )

    def __str__(self) -> str:
        return f"Customer({self.customer_id}: {self.name}, {self.currency})"
