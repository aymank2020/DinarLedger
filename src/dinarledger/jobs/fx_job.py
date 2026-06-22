"""Daily FX rate snapshot job.

Updates FX rates from a provided rate source (a callable that returns
the latest rates).  In production this would call an external API;
in tests it can be replaced with a deterministic function.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from dinarledger.fx.rates import FXRate


@dataclass(frozen=True)
class FXRateUpdateSummary:
    """Summary of an FX rate update job execution."""

    run_date: str
    rates_updated: int
    pairs: list[str]

    def __str__(self) -> str:
        return (
            f"FXRateUpdate({self.run_date}: "
            f"{self.rates_updated} rates updated)"
        )


class FXRateJob:
    """Daily FX rate snapshot job.

    Parameters:
        rate_source: A callable that accepts a ``datetime`` and returns
            a list of :class:`FXRate` objects for that date.
    """

    def __init__(
        self,
        rate_source: callable | None = None,
    ) -> None:
        self._rate_source = rate_source
        self._latest_rates: dict[str, FXRate] = {}

    def run(self, current_time: datetime) -> FXRateUpdateSummary:
        """Fetch and store the latest FX rates.

        Returns an :class:`FXRateUpdateSummary`.
        """
        if self._rate_source is None:
            return FXRateUpdateSummary(
                run_date=current_time.date().isoformat(),
                rates_updated=0,
                pairs=[],
            )

        try:
            rates: list[FXRate] = self._rate_source(current_time)
        except Exception:
            return FXRateUpdateSummary(
                run_date=current_time.date().isoformat(),
                rates_updated=0,
                pairs=[],
            )

        updated = 0
        pairs: list[str] = []

        for rate in rates:
            key = f"{rate.base}/{rate.quote}"
            self._latest_rates[key] = rate
            pairs.append(key)
            updated += 1

        return FXRateUpdateSummary(
            run_date=current_time.date().isoformat(),
            rates_updated=updated,
            pairs=pairs,
        )

    def __call__(self, current_time: datetime) -> FXRateUpdateSummary:
        """Scheduler-compatible entry point."""
        return self.run(current_time)

    @property
    def latest_rates(self) -> dict[str, FXRate]:
        """Most recently fetched rates keyed by ``BASE/QUOTE``."""
        return dict(self._latest_rates)
