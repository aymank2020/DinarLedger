"""Multi-element arrangement allocation — IFRS 15 transaction price allocation.

When a contract bundles multiple performance obligations the transaction
price is allocated to each obligation in proportion to its standalone
selling price (IFRS 15.73-86). For arrangements that include obligations
without observable standalone prices, the *residual approach* assigns the
remainder of the transaction price to those uncertain obligations after
the known-SSP obligations are allocated their full prices.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from dinarledger.core.money import Money, zero
from dinarledger.revenue.recognition import (
    PerformanceObligation,
    _allocated_price,
    _total_standalone_price,
)


def allocate_transaction_price(
    obligations: list[PerformanceObligation],
    total_price: Money,
) -> list[tuple[PerformanceObligation, Money]]:
    """Allocate *total_price* across *obligations* by SSP ratio.

    Each allocation is rounded to 2 decimal places using ``ROUND_HALF_UP``.
    When all obligations have zero SSP the price is split evenly as a
    fallback.
    """
    if not obligations:
        return []

    total_standalone = _total_standalone_price(obligations)

    if total_standalone.is_zero():
        count = len(obligations)
        even_amount = Money(
            amount=(total_price.amount / count).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            ),
            currency=total_price.currency,
        )
        return [(obl, even_amount) for obl in obligations]

    return [
        (obl, _allocated_price(obl, total_standalone, total_price))
        for obl in obligations
    ]


def residual_allocation(
    obligations: list[PerformanceObligation],
    total_price: Money,
) -> list[tuple[PerformanceObligation, Money]]:
    """Allocate using the IFRS 15 residual approach.

    Obligations with a non-zero standalone price get their full SSP; the
    remaining transaction price (residual) is split equally among
    obligations with zero SSP. If the residual is negative — the discount
    exceeds what the uncertain obligations would absorb — the algorithm
    falls back to proportional allocation for the known-SSP group and
    leaves the uncertain obligations at zero.
    """
    if not obligations:
        return []

    currency = total_price.currency

    known_ssp: list[tuple[PerformanceObligation, Money]] = []
    uncertain_ssp: list[PerformanceObligation] = []

    for obl in obligations:
        if obl.standalone_price.is_zero():
            uncertain_ssp.append(obl)
        else:
            known_ssp.append((obl, obl.standalone_price))

    known_ssp_total = zero(currency)
    for _, ssp in known_ssp:
        known_ssp_total = known_ssp_total + ssp

    residual = total_price - known_ssp_total

    results: list[tuple[PerformanceObligation, Money]] = []

    for obl, ssp in known_ssp:
        if residual.amount >= Decimal("0"):
            results.append((obl, ssp))
        else:
            total_standalone = _total_standalone_price(obligations)
            results.append((obl, _allocated_price(obl, total_standalone, total_price)))

    if uncertain_ssp:
        if residual.amount >= Decimal("0"):
            count = len(uncertain_ssp)
            share = Money(
                amount=(residual.amount / count).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                ),
                currency=currency,
            )
            for obl in uncertain_ssp:
                results.append((obl, share))
        else:
            for obl in uncertain_ssp:
                results.append((obl, zero(currency)))

    return results
