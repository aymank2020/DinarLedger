"""FX rate management and currency conversion.

Provides:

* :class:`FXRate` — an FX quote (base / quote pair, rate, date).
* :func:`convert` — convert a :class:`Money` amount using a given rate.
* :func:`cross_rate` — derive a cross rate via a common currency.

The rate is interpreted as ``1 unit of base = rate units of quote``.
``convert`` always multiplies, so the caller is responsible for passing
the rate in the correct direction (use :meth:`FXRate.invert` to flip).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from dinarledger.core.money import Money


@dataclass(frozen=True)
class FXRate:
    """An FX rate quote for a currency pair.

    Attributes:
        base: Base currency code (ISO 4217).
        quote: Quote currency code (ISO 4217).
        rate: Exchange rate — 1 unit of *base* = *rate* units of *quote*.
        rate_date: The effective date of the quote.
    """

    base: str
    quote: str
    rate: Decimal
    rate_date: date

    def __post_init__(self) -> None:
        if not isinstance(self.rate, Decimal):
            object.__setattr__(self, "rate", Decimal(str(self.rate)))
        if self.rate <= 0:
            raise ValueError(f"FX rate must be positive, got {self.rate}")

    def invert(self) -> FXRate:
        """Return the inverse rate (swap base/quote, take reciprocal)."""
        inverted_rate = (Decimal("1") / self.rate).quantize(
            Decimal("0.000001"), rounding=ROUND_HALF_UP
        )
        return FXRate(
            base=self.quote,
            quote=self.base,
            rate=inverted_rate,
            rate_date=self.rate_date,
        )


def convert(money: Money, target_currency: str, rate: Decimal) -> Money:
    """Convert *money* to *target_currency* using *rate*.

    Computes ``money.amount × rate`` and returns the result in
    *target_currency*. The rate must be expressed as
    ``1 source = rate target``; pass an inverted rate when going the
    other direction.
    """
    if not isinstance(rate, Decimal):
        rate = Decimal(str(rate))

    converted_amount = money.amount * rate
    return Money(
        amount=converted_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        currency=target_currency,
    )


def cross_rate(rate1: FXRate, rate2: FXRate) -> Decimal:
    """Cross rate derived from two quotes that share a common currency.

    Inspects the four possible pairings between *rate1* and *rate2* and
    multiplies (or inverts and multiplies) accordingly. Raises
    :class:`ValueError` when the two rates have no currency in common.
    """
    if rate1.base == rate2.quote:
        cross = rate2.rate * rate1.rate
        return cross.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)

    if rate1.quote == rate2.base:
        cross = rate1.rate * rate2.rate
        return cross.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)

    if rate1.base == rate2.base:
        inv = rate2.invert()
        cross = inv.rate * rate1.rate
        return cross.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)

    if rate1.quote == rate2.quote:
        inv = rate1.invert()
        cross = inv.rate * rate2.rate
        return cross.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)

    raise ValueError(
        f"No common currency between {rate1.base}/{rate1.quote} "
        f"and {rate2.base}/{rate2.quote}"
    )
