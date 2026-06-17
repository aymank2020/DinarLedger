"""Customer service — orchestrates customer onboarding, plan changes,
seat management, and credit-limit checks.

Delegates to:
* ``dinarledger.subscriptions.lifecycle`` — subscription state transitions
* ``dinarledger.subscriptions.seats`` — seat add/remove with proration
* ``dinarledger.customers.credit`` — credit-limit validation
* ``dinarledger.storage.base.Repository`` — persistence (injected)
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from dinarledger.core.enums import InvoiceStatus, SubscriptionStatus
from dinarledger.core.errors import (
    CreditLimitExceededError,
    DinarLedgerError,
    InvalidParameterError,
)
from dinarledger.core.money import Money
from dinarledger.core.types import (
    BillingPeriod,
    Customer,
    Invoice,
    Plan,
    Subscription,
)
from dinarledger.customers.credit import check_credit_limit as _check_credit
from dinarledger.subscriptions.lifecycle import (
    change_plan as _change_plan,
    subscribe as _subscribe,
)
from dinarledger.subscriptions.seats import (
    add_seats as _add_seats,
    remove_seats as _remove_seats,
)
from dinarledger.storage.base import Repository


class CustomerService:
    """Orchestrates customer lifecycle operations.

    Parameters
    ----------
    customer_repo : Repository[Customer]
        Persistence for customers.
    subscription_repo : Repository[Subscription]
        Persistence for subscriptions.
    invoice_repo : Repository[Invoice]
        Persistence for invoices (used for credit checks and summaries).
    """

    def __init__(
        self,
        customer_repo: Repository[Customer],
        subscription_repo: Repository[Subscription],
        invoice_repo: Repository[Invoice],
    ) -> None:
        self._customers = customer_repo
        self._subscriptions = subscription_repo
        self._invoices = invoice_repo

    # ── Onboarding ──────────────────────────────────────────────────────────

    def onboard_customer(
        self,
        name: str,
        currency: str,
        credit_limit: Decimal | None = None,
        *,
        customer_id: str | None = None,
        tax_exempt: bool = False,
        tax_jurisdiction: str = "",
    ) -> Customer:
        """Create a new customer, validate, and persist.

        Parameters
        ----------
        name : str
            Full name of the customer / organisation.
        currency : str
            ISO 4217 currency code.
        credit_limit : Decimal | None
            Optional credit limit in the given currency. ``None`` means
            unlimited credit.

        Returns
        -------
        Customer
            The newly created and persisted customer.
        """
        if not name or not name.strip():
            raise InvalidParameterError(
                "name", message="Customer name must not be empty"
            )

        limit_money = (
            Money(amount=credit_limit, currency=currency.upper())
            if credit_limit is not None
            else None
        )
        cid = customer_id or f"cust-{len(self._customers.get_all()) + 1}"
        customer = Customer(
            customer_id=cid,
            name=name.strip(),
            currency=currency,
            credit_limit=limit_money,
            tax_exempt=tax_exempt,
            tax_jurisdiction=tax_jurisdiction,
        )
        return self._customers.add(customer)

    # ── Plan changes ────────────────────────────────────────────────────────

    def change_plan(
        self,
        customer_id: str,
        new_plan: Plan,
        change_date: date | None = None,
    ) -> tuple[Subscription, Money]:
        """Change the plan for the customer's active subscription.

        Returns the updated subscription and the net upgrade amount
        (positive = customer owes, negative = credit).

        Raises
        ------
        DinarLedgerError
            If the customer has no active subscription.
        """
        sub = self._find_active_subscription(customer_id)
        if sub is None:
            raise DinarLedgerError(
                f"No active subscription found for customer '{customer_id}'",
                context={"customer_id": customer_id},
            )

        effective_date = change_date or date.today()
        updated, net = _change_plan(sub, new_plan, effective_date)
        self._subscriptions.update(updated)
        return updated, net

    # ── Seat management ─────────────────────────────────────────────────────

    def manage_seats(
        self,
        customer_id: str,
        delta: int,
        change_date: date | None = None,
    ) -> tuple[Subscription, Money]:
        """Add (*delta* > 0) or remove (*delta* < 0) seats.

        Returns the updated subscription and the prorated charge (positive)
        or credit (negative).

        Raises
        ------
        DinarLedgerError
            If the customer has no active subscription.
        ValueError
            If *delta* is zero.
        """
        if delta == 0:
            raise ValueError("delta must be non-zero")

        sub = self._find_active_subscription(customer_id)
        if sub is None:
            raise DinarLedgerError(
                f"No active subscription found for customer '{customer_id}'",
                context={"customer_id": customer_id},
            )

        effective_date = change_date or date.today()
        period = self._current_period(sub)

        if delta > 0:
            updated, charge = _add_seats(sub, delta, effective_date, period)
        else:
            updated, credit = _remove_seats(sub, abs(delta), effective_date, period)
            credit = -credit  # negative = credit back to customer
            self._subscriptions.update(updated)
            return updated, credit

        self._subscriptions.update(updated)
        return updated, charge

    # ── Customer summary ────────────────────────────────────────────────────

    def get_customer_summary(self, customer_id: str) -> dict[str, Any]:
        """Return a summary dict with customer, subscriptions, and invoices."""
        customer = self._customers.get(customer_id)
        if customer is None:
            raise DinarLedgerError(
                f"Customer '{customer_id}' not found",
                context={"customer_id": customer_id},
            )

        subscriptions = self._subscriptions.find({"customer_id": customer_id})
        invoices = self._invoices.find({"customer_id": customer_id})

        return {
            "customer": customer,
            "subscriptions": subscriptions,
            "invoices": invoices,
        }

    # ── Credit check ────────────────────────────────────────────────────────

    def check_credit(self, customer_id: str, amount: Money) -> bool:
        """Check whether *amount* stays within the customer's credit limit.

        Returns ``True`` when the charge is allowed.
        Raises :class:`CreditLimitExceededError` when the limit is breached.
        """
        customer = self._customers.get(customer_id)
        if customer is None:
            raise DinarLedgerError(
                f"Customer '{customer_id}' not found",
                context={"customer_id": customer_id},
            )

        pending = self._invoices.find({"customer_id": customer_id})
        open_invoices = [
            inv for inv in pending
            if inv.status in {InvoiceStatus.OPEN, InvoiceStatus.OVERDUE}
        ]

        allowed = _check_credit(customer, open_invoices, amount)
        if not allowed:
            raise CreditLimitExceededError(
                customer_id=customer_id,
                attempted_amount=amount,
            )
        return True

    # ── Internal helpers ────────────────────────────────────────────────────

    def _find_active_subscription(self, customer_id: str) -> Subscription | None:
        """Return the first active subscription for *customer_id*."""
        subs = self._subscriptions.find({"customer_id": customer_id})
        for sub in subs:
            if sub.status in {SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL}:
                return sub
        return None

    @staticmethod
    def _current_period(sub: Subscription) -> BillingPeriod:
        """Derive a BillingPeriod from the subscription's dates."""
        start = sub.current_period_start or sub.start_date
        end = sub.current_period_end or sub.end_date or sub.start_date
        return BillingPeriod(start_date=start, end_date=end)
