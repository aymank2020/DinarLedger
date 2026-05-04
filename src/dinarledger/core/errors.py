"""
dinarledger.core.errors — Custom exception hierarchy.

Every public exception inherits from :class:`DinarLedgerError` so that callers
can catch the entire family with a single ``except DinarLedgerError`` clause.
The hierarchy mirrors the major domain areas of the system:

    DinarLedgerError
    ├── InvalidParameterError
    ├── SubscriptionError
    │   ├── SubscriptionStateError
    │   └── PlanNotFoundError
    ├── BillingError
    │   ├── InvoiceError
    │   ├── CreditLimitExceededError
    │   └── ProrationError
    ├── RevenueError
    │   ├── RecognitionError
    │   └── AllocationError
    ├── PaymentError
    │   ├── PaymentAllocationError
    │   └── ReconciliationError
    ├── FXError
    │   ├── RateNotFoundError
    │   └── CurrencyMismatchError
    └── TaxError
        └── ExemptionError
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

class DinarLedgerError(Exception):
    """Root exception for all DinarLedger domain errors.

    Parameters
    ----------
    message : str
        Human-readable description of the error.
    context : dict[str, Any] | None
        Optional structured context that callers can inspect programmatically
        (e.g. ``{"customer_id": "C-001", "currency": "KWD"}``).
    """

    def __init__(self, message: str, context: dict[str, Any] | None = None) -> None:
        self.context: dict[str, Any] = context or {}
        super().__init__(message)

    def __str__(self) -> str:
        base = super().__str__()
        if self.context:
            ctx = ", ".join(f"{k}={v!r}" for k, v in sorted(self.context.items()))
            return f"{base} [{ctx}]"
        return base


# ---------------------------------------------------------------------------
# Parameter validation
# ---------------------------------------------------------------------------

class InvalidParameterError(DinarLedgerError):
    """Raised when a caller supplies an invalid or out-of-range parameter.

    Attributes
    ----------
    parameter_name : str
        The name of the offending parameter.
    """

    def __init__(
        self,
        parameter_name: str,
        message: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        self.parameter_name = parameter_name
        msg = message or f"Invalid value for parameter '{parameter_name}'"
        ctx: dict[str, Any] = {"parameter_name": parameter_name}
        if context:
            ctx.update(context)
        super().__init__(msg, context=ctx)

    def __str__(self) -> str:
        return f"InvalidParameter({self.parameter_name}): {self.args[0]}"


# ---------------------------------------------------------------------------
# Subscription errors
# ---------------------------------------------------------------------------

class SubscriptionError(DinarLedgerError):
    """Base for all subscription-related errors."""

    def __init__(
        self,
        message: str,
        sub_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        ctx = context or {}
        if sub_id is not None:
            ctx.setdefault("sub_id", sub_id)
        self.sub_id = sub_id
        super().__init__(message, context=ctx)


class SubscriptionStateError(SubscriptionError):
    """Raised when a subscription state transition is not allowed.

    For example, attempting to reactivate a subscription that is already
    ``ACTIVE`` or cancelling one that is ``EXPIRED``.
    """

    def __init__(
        self,
        sub_id: str,
        current_state: str,
        attempted_action: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        self.current_state = current_state
        self.attempted_action = attempted_action
        msg = (
            f"Cannot perform '{attempted_action}' on subscription "
            f"'{sub_id}' in state '{current_state}'"
        )
        ctx: dict[str, Any] = {"current_state": current_state, "attempted_action": attempted_action}
        if context:
            ctx.update(context)
        super().__init__(msg, sub_id=sub_id, context=ctx)

    def __str__(self) -> str:
        return (
            f"SubscriptionStateError: {self.current_state} -> "
            f"{self.attempted_action} on {self.sub_id}"
        )


class PlanNotFoundError(SubscriptionError):
    """Raised when a referenced plan does not exist."""

    def __init__(
        self,
        plan_id: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        self.plan_id = plan_id
        msg = f"Plan '{plan_id}' not found"
        ctx: dict[str, Any] = {"plan_id": plan_id}
        if context:
            ctx.update(context)
        super().__init__(msg, context=ctx)

    def __str__(self) -> str:
        return f"PlanNotFoundError: plan_id={self.plan_id!r}"


# ---------------------------------------------------------------------------
# Billing errors
# ---------------------------------------------------------------------------

class BillingError(DinarLedgerError):
    """Base for all billing-related errors."""

    def __init__(
        self,
        message: str,
        customer_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        ctx = context or {}
        if customer_id is not None:
            ctx.setdefault("customer_id", customer_id)
        self.customer_id = customer_id
        super().__init__(message, context=ctx)


class InvoiceError(BillingError):
    """Raised when an invoice cannot be created, modified, or finalized."""

    def __init__(
        self,
        message: str,
        invoice_id: str | None = None,
        customer_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        self.invoice_id = invoice_id
        ctx = context or {}
        if invoice_id is not None:
            ctx.setdefault("invoice_id", invoice_id)
        super().__init__(message, customer_id=customer_id, context=ctx)

    def __str__(self) -> str:
        inv = f"invoice={self.invoice_id!r}" if self.invoice_id else "no-invoice"
        return f"InvoiceError({inv}): {self.args[0]}"


class CreditLimitExceededError(BillingError):
    """Raised when an invoice would push a customer past their credit limit.

    Attributes
    ----------
    current_balance : Any | None
        The outstanding balance before this operation.
    credit_limit : Any | None
        The configured credit limit.
    attempted_amount : Any | None
        The amount of the rejected charge.
    """

    def __init__(
        self,
        customer_id: str,
        attempted_amount: Any | None = None,
        current_balance: Any | None = None,
        credit_limit: Any | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        self.current_balance = current_balance
        self.credit_limit = credit_limit
        self.attempted_amount = attempted_amount
        msg = (
            f"Credit limit exceeded for customer '{customer_id}': "
            f"attempted {attempted_amount}, balance {current_balance}, "
            f"limit {credit_limit}"
        )
        ctx: dict[str, Any] = {}
        if attempted_amount is not None:
            ctx["attempted_amount"] = str(attempted_amount)
        if current_balance is not None:
            ctx["current_balance"] = str(current_balance)
        if credit_limit is not None:
            ctx["credit_limit"] = str(credit_limit)
        if context:
            ctx.update(context)
        super().__init__(msg, customer_id=customer_id, context=ctx)

    def __str__(self) -> str:
        return (
            f"CreditLimitExceeded: customer={self.customer_id!r}, "
            f"attempted={self.attempted_amount}, balance={self.current_balance}, "
            f"limit={self.credit_limit}"
        )


class ProrationError(BillingError):
    """Raised when a proration calculation fails or produces an invalid result."""

    def __init__(
        self,
        message: str,
        period_start: str | None = None,
        period_end: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        self.period_start = period_start
        self.period_end = period_end
        ctx: dict[str, Any] = {}
        if period_start is not None:
            ctx["period_start"] = period_start
        if period_end is not None:
            ctx["period_end"] = period_end
        if context:
            ctx.update(context)
        super().__init__(message, context=ctx)

    def __str__(self) -> str:
        period = ""
        if self.period_start and self.period_end:
            period = f" [{self.period_start}..{self.period_end}]"
        return f"ProrationError{period}: {self.args[0]}"


# ---------------------------------------------------------------------------
# Revenue errors
# ---------------------------------------------------------------------------

class RevenueError(DinarLedgerError):
    """Base for all revenue recognition errors."""

    def __init__(
        self,
        message: str,
        contract_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        ctx = context or {}
        if contract_id is not None:
            ctx.setdefault("contract_id", contract_id)
        self.contract_id = contract_id
        super().__init__(message, context=ctx)


class RecognitionError(RevenueError):
    """Raised when a revenue recognition entry cannot be created or posted.

    Typical causes: performance obligation not satisfied, amounts already
    fully recognized, or period-lock violations.
    """

    def __init__(
        self,
        message: str,
        contract_id: str | None = None,
        performance_obligation: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        self.performance_obligation = performance_obligation
        ctx: dict[str, Any] = {}
        if performance_obligation is not None:
            ctx["performance_obligation"] = performance_obligation
        if context:
            ctx.update(context)
        super().__init__(message, contract_id=contract_id, context=ctx)

    def __str__(self) -> str:
        pob = f", pob={self.performance_obligation!r}" if self.performance_obligation else ""
        return f"RecognitionError(contract={self.contract_id!r}{pob}): {self.args[0]}"


class AllocationError(RevenueError):
    """Raised when standalone-selling-price allocation fails under IFRS 15.

    This typically occurs when the sum of allocated amounts does not
    reconcile to the transaction price, or when a performance obligation
    has no observable standalone selling price.
    """

    def __init__(
        self,
        message: str,
        contract_id: str | None = None,
        transaction_price: Any | None = None,
        allocated_total: Any | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        self.transaction_price = transaction_price
        self.allocated_total = allocated_total
        ctx: dict[str, Any] = {}
        if transaction_price is not None:
            ctx["transaction_price"] = str(transaction_price)
        if allocated_total is not None:
            ctx["allocated_total"] = str(allocated_total)
        if context:
            ctx.update(context)
        super().__init__(message, contract_id=contract_id, context=ctx)

    def __str__(self) -> str:
        return (
            f"AllocationError(contract={self.contract_id!r}): {self.args[0]} "
            f"(tx_price={self.transaction_price}, allocated={self.allocated_total})"
        )


# ---------------------------------------------------------------------------
# Payment errors
# ---------------------------------------------------------------------------

class PaymentError(DinarLedgerError):
    """Base for all payment-related errors."""

    def __init__(
        self,
        message: str,
        payment_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        ctx = context or {}
        if payment_id is not None:
            ctx.setdefault("payment_id", payment_id)
        self.payment_id = payment_id
        super().__init__(message, context=ctx)


class PaymentAllocationError(PaymentError):
    """Raised when a payment cannot be allocated across invoices.

    This is distinct from :class:`AllocationError` (revenue): the payment
    variant deals with applying cash receipts to outstanding invoices, not
    with IFRS 15 SSP allocation.
    """

    def __init__(
        self,
        message: str,
        payment_id: str | None = None,
        invoice_ids: list[str] | None = None,
        unapplied_amount: Any | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        self.invoice_ids = invoice_ids or []
        self.unapplied_amount = unapplied_amount
        ctx: dict[str, Any] = {}
        if invoice_ids:
            ctx["invoice_ids"] = invoice_ids
        if unapplied_amount is not None:
            ctx["unapplied_amount"] = str(unapplied_amount)
        if context:
            ctx.update(context)
        super().__init__(message, payment_id=payment_id, context=ctx)

    def __str__(self) -> str:
        invs = ", ".join(self.invoice_ids) if self.invoice_ids else "none"
        return (
            f"PaymentAllocationError: {self.args[0]} "
            f"(invoices=[{invs}], unapplied={self.unapplied_amount})"
        )


class ReconciliationError(PaymentError):
    """Raised when a payment cannot be reconciled with bank records."""

    def __init__(
        self,
        message: str,
        payment_id: str | None = None,
        expected_amount: Any | None = None,
        actual_amount: Any | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        self.expected_amount = expected_amount
        self.actual_amount = actual_amount
        ctx: dict[str, Any] = {}
        if expected_amount is not None:
            ctx["expected_amount"] = str(expected_amount)
        if actual_amount is not None:
            ctx["actual_amount"] = str(actual_amount)
        if context:
            ctx.update(context)
        super().__init__(message, payment_id=payment_id, context=ctx)

    def __str__(self) -> str:
        return (
            f"ReconciliationError: {self.args[0]} "
            f"(expected={self.expected_amount}, actual={self.actual_amount})"
        )


# ---------------------------------------------------------------------------
# FX errors
# ---------------------------------------------------------------------------

class FXError(DinarLedgerError):
    """Base for all foreign-exchange errors."""

    def __init__(
        self,
        message: str,
        base_currency: str | None = None,
        quote_currency: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        ctx: dict[str, Any] = {}
        if base_currency is not None:
            ctx["base_currency"] = base_currency
        if quote_currency is not None:
            ctx["quote_currency"] = quote_currency
        if context:
            ctx.update(context)
        self.base_currency = base_currency
        self.quote_currency = quote_currency
        super().__init__(message, context=ctx)


class RateNotFoundError(FXError):
    """Raised when no FX rate is available for the requested pair and date."""

    def __init__(
        self,
        base_currency: str,
        quote_currency: str,
        as_of: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        self.as_of = as_of
        pair = f"{base_currency}/{quote_currency}"
        date_clause = f" as of {as_of}" if as_of else ""
        msg = f"No FX rate found for {pair}{date_clause}"
        ctx: dict[str, Any] = {}
        if as_of is not None:
            ctx["as_of"] = as_of
        if context:
            ctx.update(context)
        super().__init__(
            msg,
            base_currency=base_currency,
            quote_currency=quote_currency,
            context=ctx,
        )

    def __str__(self) -> str:
        return (
            f"RateNotFoundError: {self.base_currency}/{self.quote_currency}"
            f"{'@' + self.as_of if self.as_of else ''}"
        )


class CurrencyMismatchError(FXError):
    """Raised when an operation involves two different currencies without
    an explicit conversion step."""

    def __init__(
        self,
        expected: str,
        actual: str,
        operation: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        self.expected = expected
        self.actual = actual
        self.operation = operation
        op_clause = f" during '{operation}'" if operation else ""
        msg = f"Currency mismatch{op_clause}: expected {expected}, got {actual}"
        ctx: dict[str, Any] = {}
        if operation:
            ctx["operation"] = operation
        if context:
            ctx.update(context)
        super().__init__(
            msg, base_currency=expected, quote_currency=actual, context=ctx
        )

    def __str__(self) -> str:
        return f"CurrencyMismatchError: expected={self.expected!r}, actual={self.actual!r}"


# ---------------------------------------------------------------------------
# Tax errors
# ---------------------------------------------------------------------------

class TaxError(DinarLedgerError):
    """Base for all tax-related errors."""

    def __init__(
        self,
        message: str,
        jurisdiction: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        ctx = context or {}
        if jurisdiction is not None:
            ctx.setdefault("jurisdiction", jurisdiction)
        self.jurisdiction = jurisdiction
        super().__init__(message, context=ctx)


class ExemptionError(TaxError):
    """Raised when a tax exemption cannot be applied or is invalid.

    For example, an expired exemption certificate or a jurisdiction that
    does not recognise the exemption category.
    """

    def __init__(
        self,
        message: str,
        jurisdiction: str | None = None,
        exemption_id: str | None = None,
        reason: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        self.exemption_id = exemption_id
        self.reason = reason
        ctx: dict[str, Any] = {}
        if exemption_id is not None:
            ctx["exemption_id"] = exemption_id
        if reason is not None:
            ctx["reason"] = reason
        if context:
            ctx.update(context)
        super().__init__(message, jurisdiction=jurisdiction, context=ctx)

    def __str__(self) -> str:
        parts = [f"jurisdiction={self.jurisdiction!r}"]
        if self.exemption_id:
            parts.append(f"exemption_id={self.exemption_id!r}")
        if self.reason:
            parts.append(f"reason={self.reason!r}")
        return f"ExemptionError({', '.join(parts)}): {self.args[0]}"
