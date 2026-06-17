"""FX service — orchestrates rate management, currency conversion,
and month-end AR revaluation.

Delegates to:
* ``dinarledger.fx.rates`` — FXRate, convert, cross_rate
* ``dinarledger.fx.revaluation`` — unrealized_gain, revalue_ar
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from dinarledger.core.errors import FXError, RateNotFoundError
from dinarledger.core.money import Money
from dinarledger.core.types import Invoice
from dinarledger.fx.rates import FXRate, convert as _convert, cross_rate as _cross_rate
from dinarledger.fx.revaluation import revalue_ar as _revalue_ar


class FXService:
    """Orchestrates foreign-exchange operations.

    Maintains an in-memory rate store that can be bulk-updated. For
    production use, inject a persistent rate provider instead.

    Parameters
    ----------
    rates : dict[str, FXRate] | None
        Initial rate dictionary keyed by ``"{base}/{quote}"``.
    """

    def __init__(self, rates: dict[str, FXRate] | None = None) -> None:
        self._rates: dict[str, FXRate] = dict(rates) if rates else {}

    # ── Rate management ─────────────────────────────────────────────────────

    def update_rates(self, rates_dict: dict[str, FXRate]) -> None:
        """Bulk update FX rates.

        Parameters
        ----------
        rates_dict : dict[str, FXRate]
            Rates keyed by ``"{base}/{quote}"`` (e.g. ``"USD/EUR"``).
        """
        self._rates.update(rates_dict)

    def get_rate(self, base: str, quote: str) -> FXRate | None:
        """Retrieve a stored rate for the given pair, or ``None``."""
        return self._rates.get(f"{base}/{quote}")

    # ── Conversion ──────────────────────────────────────────────────────────

    def convert_amount(
        self,
        money: Money,
        target_currency: str,
        rates: dict[str, FXRate] | None = None,
    ) -> Money:
        """Convert *money* to *target_currency* using available rates.

        Parameters
        ----------
        money : Money
            Amount to convert.
        target_currency : str
            Target ISO 4217 currency code.
        rates : dict[str, FXRate] | None
            Optional rate dictionary; falls back to the service's
            internal store when not provided.

        Raises
        ------
        RateNotFoundError
            When no rate is available for the conversion pair.
        """
        if money.currency == target_currency.upper():
            return money

        rate_store = rates if rates is not None else self._rates

        # Direct rate: base/source → quote/target
        key = f"{money.currency}/{target_currency.upper()}"
        fx = rate_store.get(key)
        if fx is not None:
            return _convert(money, target_currency, fx.rate)

        # Try inverted rate
        inv_key = f"{target_currency.upper()}/{money.currency}"
        fx_inv = rate_store.get(inv_key)
        if fx_inv is not None:
            return _convert(money, target_currency, fx_inv.invert().rate)

        # Try cross rate via a common pivot (USD)
        pivot = "USD"
        if money.currency != pivot and target_currency.upper() != pivot:
            # Resolve source→pivot, trying both directions
            source_to_pivot = rate_store.get(f"{money.currency}/{pivot}")
            if source_to_pivot is None:
                pivot_to_source = rate_store.get(f"{pivot}/{money.currency}")
                if pivot_to_source is not None:
                    source_to_pivot = pivot_to_source.invert()

            # Resolve pivot→target, trying both directions
            pivot_to_target = rate_store.get(f"{pivot}/{target_currency.upper()}")
            if pivot_to_target is None:
                target_to_pivot = rate_store.get(f"{target_currency.upper()}/{pivot}")
                if target_to_pivot is not None:
                    pivot_to_target = target_to_pivot.invert()

            if source_to_pivot is not None and pivot_to_target is not None:
                cross = _cross_rate(source_to_pivot, pivot_to_target)
                return _convert(money, target_currency, cross)

        raise RateNotFoundError(
            base_currency=money.currency,
            quote_currency=target_currency,
        )

    # ── Revaluation ─────────────────────────────────────────────────────────

    def schedule_revaluation(
        self,
        invoices: list[Invoice],
        rates: dict[str, Decimal],
        base_currency: str = "USD",
    ) -> list[tuple[str, Money]]:
        """Revalue foreign-currency AR invoices at month-end rates.

        Delegates to :func:`dinarledger.fx.revaluation.revalue_ar`.
        """
        return _revalue_ar(invoices, rates, base_currency)
