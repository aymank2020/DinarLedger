"""
dinarledger.utils.decimal_helpers — Decimal utility functions.

Rounding, safe conversion, and percentage helpers for financial
calculations using :class:`decimal.Decimal`.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_EVEN, ROUND_HALF_UP


def round_half_even(value: Decimal, places: int = 2) -> Decimal:
    """Round *value* using banker's rounding (ROUND_HALF_EVEN).

    This is the default rounding mode in DinarLedger for monetary amounts.

    Parameters
    ----------
    value : Decimal
        The value to round.
    places : int, optional
        Number of decimal places (default 2).

    Returns
    -------
    Decimal
        The rounded value.
    """
    exp = Decimal("1") if places == 0 else Decimal("0." + "0" * (places - 1) + "1")
    return value.quantize(exp, rounding=ROUND_HALF_EVEN)


def round_half_up(value: Decimal, places: int = 2) -> Decimal:
    """Round *value* using standard rounding (ROUND_HALF_UP).

    Required by many tax jurisdictions and used for proration and
    FX conversion in DinarLedger.

    Parameters
    ----------
    value : Decimal
        The value to round.
    places : int, optional
        Number of decimal places (default 2).

    Returns
    -------
    Decimal
        The rounded value.
    """
    exp = Decimal("1") if places == 0 else Decimal("0." + "0" * (places - 1) + "1")
    return value.quantize(exp, rounding=ROUND_HALF_UP)


def safe_decimal(value: Decimal | int | float | str) -> Decimal:
    """Convert *value* to :class:`Decimal` safely.

    Floats are converted via their string representation to avoid
    binary-floating-point artefacts (e.g. ``0.1`` becomes
    ``Decimal('0.1')``, not ``Decimal('0.1000000000000000055511151231')``).

    Parameters
    ----------
    value : Decimal | int | float | str
        The value to convert.

    Returns
    -------
    Decimal
        The converted decimal.

    Raises
    ------
    TypeError
        If *value* is not a supported type.
    """
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, str):
        return Decimal(value)
    raise TypeError(
        f"Cannot convert {type(value).__name__} to Decimal; "
        f"expected Decimal, int, float, or str"
    )


def percentage(part: Decimal, whole: Decimal) -> Decimal:
    """Calculate the percentage that *part* represents of *whole*.

    Returns a value in the range ``[0, 1]`` when *part* <= *whole*,
    or > 1 when *part* exceeds *whole*.

    Parameters
    ----------
    part : Decimal
        The part value.
    whole : Decimal
        The whole (base) value.

    Returns
    -------
    Decimal
        ``part / whole`` quantised to 6 decimal places.

    Raises
    ------
    ZeroDivisionError
        If *whole* is zero.
    """
    if whole == Decimal("0"):
        raise ZeroDivisionError("Cannot compute percentage with whole=0")
    result = part / whole
    return result.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
