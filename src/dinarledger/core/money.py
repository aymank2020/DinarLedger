"""
dinarledger.core.money — Decimal-based monetary arithmetic.

Provides a :class:`Money` value type that enforces currency-safe
operations and uses :class:`decimal.Decimal` internally to avoid
floating-point rounding pitfalls. ``Money`` is a frozen dataclass and
therefore immutable; every arithmetic operation returns a fresh instance.

Rounding follows banker's rounding (``ROUND_HALF_EVEN``) by default to
match the convention used in most financial jurisdictions. Currency
mismatches raise :class:`~dinarledger.core.errors.CurrencyMismatchError`
rather than silently converting.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_EVEN
from typing import Iterable

from .errors import CurrencyMismatchError


_TWO_PLACES = Decimal("0.01")


@dataclass(frozen=True)
class Money:
    """Immutable monetary amount in a specific currency.

    Parameters
    ----------
    amount : Decimal
        The monetary amount.  Must be a :class:`~decimal.Decimal`; use
        :meth:`from_float` for ``float`` values.
    currency : str
        ISO 4217 currency code (e.g. ``"KWD"``, ``"USD"``, ``"EUR"``).
        Stored in upper-case.
    """

    amount: Decimal
    currency: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "currency", self.currency.upper())
        if not isinstance(self.amount, Decimal):
            raise TypeError(
                f"Money.amount must be a Decimal, got {type(self.amount).__name__}. "
                f"Use Money.from_float() for float values."
            )

    # -- String representations ------------------------------------------------

    def __str__(self) -> str:
        return f"{self.amount:.2f} {self.currency}"

    def __repr__(self) -> str:
        return f"Money(amount=Decimal('{self.amount}'), currency='{self.currency}')"

    # -- Currency guard --------------------------------------------------------

    def _same_currency(self, other: Money) -> None:
        if self.currency != other.currency:
            raise CurrencyMismatchError(
                expected=self.currency,
                actual=other.currency,
                operation=f"{self!r} operation with {other!r}",
            )

    # -- Arithmetic -----------------------------------------------------------

    def __add__(self, other: Money) -> Money:
        self._same_currency(other)
        return Money(amount=self.amount + other.amount, currency=self.currency)

    def __sub__(self, other: Money) -> Money:
        self._same_currency(other)
        return Money(amount=self.amount - other.amount, currency=self.currency)

    def __mul__(self, factor: Decimal | int | float) -> Money:
        if isinstance(factor, float):
            factor = Decimal(str(factor))
        elif not isinstance(factor, (Decimal, int)):
            return NotImplemented
        return Money(amount=self.amount * factor, currency=self.currency)

    def __rmul__(self, factor: Decimal | int | float) -> Money:
        return self.__mul__(factor)

    def __neg__(self) -> Money:
        return Money(amount=-self.amount, currency=self.currency)

    # -- Comparisons ----------------------------------------------------------

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        if self.currency != other.currency:
            return False
        return self.amount == other.amount

    def __lt__(self, other: Money) -> bool:
        self._same_currency(other)
        return self.amount < other.amount

    def __le__(self, other: Money) -> bool:
        self._same_currency(other)
        return self.amount <= other.amount

    def __gt__(self, other: Money) -> bool:
        self._same_currency(other)
        return self.amount > other.amount

    def __ge__(self, other: Money) -> bool:
        self._same_currency(other)
        return self.amount >= other.amount

    def __hash__(self) -> int:
        return hash((self.amount, self.currency))

    # -- Rounding -------------------------------------------------------------

    def quantize(self, exp: Decimal = _TWO_PLACES) -> Money:
        """Return a new ``Money`` with the amount rounded to *exp* using
        ``ROUND_HALF_EVEN``. Defaults to two decimal places.
        """
        return Money(
            amount=self.amount.quantize(exp, rounding=ROUND_HALF_EVEN),
            currency=self.currency,
        )

    # -- Predicates -----------------------------------------------------------

    def is_zero(self) -> bool:
        """``True`` if the amount is exactly zero."""
        return self.amount == Decimal("0")

    def is_negative(self) -> bool:
        """``True`` if the amount is less than zero."""
        return self.amount < Decimal("0")

    # -- Allocation -----------------------------------------------------------

    def allocate(self, ratios: list[Decimal]) -> list[Money]:
        """Split this amount across *ratios*.

        Ratios are normalised so they sum to 1.0, allowing whole-number
        ratios such as ``[3, 2, 1]``. Each share is quantised to two
        decimal places; the last bucket receives the rounding remainder
        so that ``sum(result) == self.quantize()`` for the common cases.

        Raises
        ------
        ValueError
            If *ratios* is empty or all entries are zero.
        """
        if not ratios:
            raise ValueError("ratios must be a non-empty list")

        total_ratio = sum(ratios)
        if total_ratio == 0:
            raise ValueError("At least one ratio must be non-zero")

        normalised = [r / total_ratio for r in ratios]

        quantised_total = self.quantize().amount
        shares: list[Money] = []
        allocated = Decimal("0")

        for nr in normalised[:-1]:
            share_amount = (quantised_total * nr).quantize(
                _TWO_PLACES, rounding=ROUND_HALF_EVEN
            )
            shares.append(Money(amount=share_amount, currency=self.currency))
            allocated += share_amount

        last_amount = quantised_total - allocated
        shares.append(Money(amount=last_amount, currency=self.currency))

        return shares

    # -- Factories ------------------------------------------------------------

    @classmethod
    def zero(cls, currency: str = "USD") -> Money:
        """Return a zero-amount :class:`Money` in the given *currency*."""
        return Money(amount=Decimal("0"), currency=currency)

    @classmethod
    def from_float(cls, amount: float, currency: str) -> Money:
        """Create a :class:`Money` from a ``float`` via its string
        representation. Use :meth:`quantize` afterwards if you need a
        clean two-decimal result.
        """
        return cls(amount=Decimal(str(amount)), currency=currency)


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def sum_money(values: Iterable[Money], currency: str | None = None) -> Money:
    """Sum an iterable of :class:`Money` values.

    All values must share the same currency; provide *currency*
    explicitly to support the empty-iterable case.
    """
    iterator = iter(values)
    try:
        first = next(iterator)
    except StopIteration:
        if currency is None:
            raise ValueError("Cannot sum empty iterable without an explicit currency")
        return zero(currency)

    expected = currency or first.currency
    if first.currency != expected:
        raise CurrencyMismatchError(
            expected=expected, actual=first.currency, operation="sum_money"
        )

    total_amount = first.amount
    for item in iterator:
        if item.currency != expected:
            raise CurrencyMismatchError(
                expected=expected, actual=item.currency, operation="sum_money"
            )
        total_amount += item.amount

    return Money(amount=total_amount, currency=expected)


def zero(currency: str) -> Money:
    """Return a zero-amount :class:`Money` in the given *currency*."""
    return Money(amount=Decimal("0"), currency=currency)
