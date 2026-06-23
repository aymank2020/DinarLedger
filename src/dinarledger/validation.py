"""
dinarledger.validation — Input validators.

Each validator checks a single domain rule and raises
:class:`~dinarledger.core.errors.InvalidParameterError` on failure.
Validators return the cleaned/normalised value on success, making them
suitable for use in ``__post_init__`` or API-layer validation.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

from dinarledger.core.errors import InvalidParameterError


# ---------------------------------------------------------------------------
# Currency
# ---------------------------------------------------------------------------

_ISO_4217_PATTERN = re.compile(r"^[A-Z]{3}$")


def validate_currency_code(code: str) -> str:
    """Validate an ISO 4217 currency code (3 uppercase letters).

    Parameters
    ----------
    code : str
        The currency code to validate.

    Returns
    -------
    str
        The uppercased code if valid.

    Raises
    ------
    InvalidParameterError
        If *code* is not a 3-letter alphabetic string.
    """
    if not isinstance(code, str):
        raise InvalidParameterError(
            "currency_code",
            message=f"currency_code must be a string, got {type(code).__name__}",
        )
    upper = code.upper()
    if not _ISO_4217_PATTERN.match(upper):
        raise InvalidParameterError(
            "currency_code",
            message=(
                f"currency_code must be 3 uppercase letters (ISO 4217), "
                f"got '{code}'"
            ),
        )
    return upper


# ---------------------------------------------------------------------------
# Date
# ---------------------------------------------------------------------------

def validate_iso_date(s: str) -> date:
    """Validate and parse an ISO 8601 date string (``YYYY-MM-DD``).

    Parameters
    ----------
    s : str
        The date string to validate.

    Returns
    -------
    date
        The parsed date.

    Raises
    ------
    InvalidParameterError
        If *s* is not a valid ISO date string.
    """
    if not isinstance(s, str):
        raise InvalidParameterError(
            "iso_date",
            message=f"iso_date must be a string, got {type(s).__name__}",
        )
    try:
        return date.fromisoformat(s)
    except ValueError:
        raise InvalidParameterError(
            "iso_date",
            message=f"Invalid ISO date string: '{s}'. Expected format: YYYY-MM-DD",
        )


# ---------------------------------------------------------------------------
# Decimal / Money
# ---------------------------------------------------------------------------

def validate_positive_decimal(value: Decimal | int | float | str) -> Decimal:
    """Validate that *value* is a positive Decimal.

    Converts int, float, and str to Decimal first.  Raises on zero or
    negative values.

    Parameters
    ----------
    value : Decimal | int | float | str
        The value to validate.

    Returns
    -------
    Decimal
        The validated (positive) decimal.

    Raises
    ------
    InvalidParameterError
        If *value* is not positive.
    """
    if isinstance(value, float):
        d = Decimal(str(value))
    elif not isinstance(value, Decimal):
        try:
            d = Decimal(str(value))
        except Exception:
            raise InvalidParameterError(
                "value",
                message=f"Cannot convert {value!r} to Decimal",
            )
    else:
        d = value

    if d <= Decimal("0"):
        raise InvalidParameterError(
            "value",
            message=f"Value must be positive, got {d}",
        )
    return d


# ---------------------------------------------------------------------------
# Billing cycle
# ---------------------------------------------------------------------------

_VALID_BILLING_CYCLES = ("monthly", "quarterly", "annual")


def validate_billing_cycle(cycle: str) -> str:
    """Validate a billing cycle string.

    Parameters
    ----------
    cycle : str
        The billing cycle to validate.

    Returns
    -------
    str
        The lowercased cycle if valid.

    Raises
    ------
    InvalidParameterError
        If *cycle* is not one of ``monthly``, ``quarterly``, or ``annual``.
    """
    if not isinstance(cycle, str):
        raise InvalidParameterError(
            "billing_cycle",
            message=f"billing_cycle must be a string, got {type(cycle).__name__}",
        )
    lower = cycle.lower()
    if lower not in _VALID_BILLING_CYCLES:
        raise InvalidParameterError(
            "billing_cycle",
            message=(
                f"billing_cycle must be one of {_VALID_BILLING_CYCLES}, "
                f"got '{cycle}'"
            ),
        )
    return lower


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_email(email: str) -> str:
    """Validate a basic email format (contains ``@`` and a domain).

    This is **not** a full RFC 5322 validator — it rejects obviously
    malformed addresses while accepting valid ones.

    Parameters
    ----------
    email : str
        The email address to validate.

    Returns
    -------
    str
        The lowercased email if valid.

    Raises
    ------
    InvalidParameterError
        If *email* does not match the basic format.
    """
    if not isinstance(email, str):
        raise InvalidParameterError(
            "email",
            message=f"email must be a string, got {type(email).__name__}",
        )
    lower = email.lower().strip()
    if not _EMAIL_PATTERN.match(lower):
        raise InvalidParameterError(
            "email",
            message=f"Invalid email format: '{email}'",
        )
    return lower


# ---------------------------------------------------------------------------
# Percentage / Rate
# ---------------------------------------------------------------------------

def validate_percentage(rate: Decimal | int | float) -> Decimal:
    """Validate that *rate* is in the inclusive range ``[0, 1]``.

    Useful for tax rates, discount rates, and allocation fractions.

    Parameters
    ----------
    rate : Decimal | int | float
        The rate to validate.

    Returns
    -------
    Decimal
        The rate as a Decimal if valid.

    Raises
    ------
    InvalidParameterError
        If *rate* is not in ``[0, 1]``.
    """
    if isinstance(rate, float):
        d = Decimal(str(rate))
    elif not isinstance(rate, Decimal):
        d = Decimal(rate)
    else:
        d = rate

    if d < Decimal("0") or d > Decimal("1"):
        raise InvalidParameterError(
            "rate",
            message=f"Rate must be between 0 and 1 inclusive, got {d}",
        )
    return d
