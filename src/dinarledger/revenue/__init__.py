"""IFRS 15 Revenue Recognition module.

Re-exports the primary API surface:

- :func:`recognize_revenue` — allocate and recognize revenue for a billing period
- :func:`deferred_revenue_schedule` — build a monthly deferred-revenue roll-forward
- :func:`allocate_transaction_price` — allocate total price across performance obligations
"""

from dinarledger.revenue.recognition import (
    PerformanceObligation,
    calculate_deferred,
    recognize_revenue,
)
from dinarledger.revenue.deferred import deferred_revenue_schedule
from dinarledger.revenue.allocation import allocate_transaction_price

__all__ = [
    "PerformanceObligation",
    "calculate_deferred",
    "recognize_revenue",
    "deferred_revenue_schedule",
    "allocate_transaction_price",
]
