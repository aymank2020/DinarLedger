"""Tax exemption rules.

Applies customer-level full exemptions and jurisdiction-based partial
exemptions to a list of line items containing tax entries from
:func:`~dinarledger.tax.calculator.calculate_tax`.
"""

from __future__ import annotations

from dinarledger.core.money import zero
from dinarledger.core.types import Customer, LineItem, TaxRate


def apply_exemption(
    customer: Customer,
    line_items: list[LineItem],
    rates: dict[str, TaxRate],
) -> list[LineItem]:
    """Apply tax exemptions for *customer* to *line_items*.

    When ``customer.tax_exempt`` is true, every tax line is replaced with
    a zero-amount line that retains the original ``tax_code`` for
    reporting. When the customer has a ``tax_jurisdiction``, only tax
    rates whose own jurisdiction differs from the customer's are zeroed
    out (foreign-tax exemption); rates matching the customer's
    jurisdiction remain untouched.
    """
    if not customer.tax_exempt and not customer.tax_jurisdiction:
        return list(line_items)

    result: list[LineItem] = []

    for item in line_items:
        if not item.is_tax:
            result.append(item)
            continue

        if not item.tax_code:
            result.append(item)
            continue

        if customer.tax_exempt:
            result.append(
                LineItem(
                    description=item.description + " [EXEMPT]",
                    amount=zero(item.amount.currency),
                    tax_code=item.tax_code,
                    is_tax=True,
                )
            )
            continue

        if customer.tax_jurisdiction:
            tax_rate = rates.get(item.tax_code)
            if tax_rate is None:
                result.append(item)
                continue

            rate_jurisdiction = getattr(tax_rate, "jurisdiction", None)

            if rate_jurisdiction is not None and rate_jurisdiction == customer.tax_jurisdiction:
                result.append(item)
            elif rate_jurisdiction is not None:
                result.append(
                    LineItem(
                        description=item.description + " [EXEMPT-FOREIGN]",
                        amount=zero(item.amount.currency),
                        tax_code=item.tax_code,
                        is_tax=True,
                    )
                )
            else:
                result.append(item)
            continue

        result.append(item)

    return result
