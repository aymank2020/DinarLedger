"""Tax calculation engine.

Computes tax for each line item individually, rounding each result
before adding it to the output (the *round-per-item* approach required
by many jurisdictions for itemised invoices).
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from dinarledger.core.money import Money
from dinarledger.core.types import LineItem, TaxRate


def calculate_tax(
    line_items: list[LineItem],
    rates: dict[str, TaxRate],
) -> list[LineItem]:
    """Insert tax lines for each taxable item in *line_items*.

    For every non-tax item with a recognised ``tax_code`` and a non-exempt
    rate, a corresponding tax :class:`LineItem` is appended right after
    the item. Items without a tax code or with an unknown code are
    copied as-is.
    """
    result: list[LineItem] = []

    for item in line_items:
        result.append(item)

        if item.is_tax:
            continue
        if not item.tax_code:
            continue

        tax_rate = rates.get(item.tax_code)
        if tax_rate is None:
            continue
        if tax_rate.is_exempt:
            continue

        tax_amount = (item.amount.amount * tax_rate.rate).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        tax_money = Money(amount=tax_amount, currency=item.amount.currency)

        result.append(
            LineItem(
                description=f"Tax ({tax_rate.code}: {tax_rate.description})",
                amount=tax_money,
                tax_code=tax_rate.code,
                is_tax=True,
            )
        )

    return result


def tax_summary(line_items: list[LineItem]) -> dict[str, Money]:
    """Group tax amounts by ``tax_code`` for reporting.

    Only line items with ``is_tax=True`` are aggregated.
    """
    summary: dict[str, Money] = {}

    for item in line_items:
        if not item.is_tax:
            continue
        if not item.tax_code:
            continue

        if item.tax_code in summary:
            summary[item.tax_code] = summary[item.tax_code] + item.amount
        else:
            summary[item.tax_code] = item.amount

    return summary
