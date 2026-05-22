"""Payment allocation and reconciliation module.

Re-exports:

- :func:`allocate_payment` — distribute a payment across invoices
- :func:`unallocated_amount` — compute remaining unallocated payment
- :func:`reconcile` — bank reconciliation (match payments to bank entries)
"""

from dinarledger.payments.allocation import allocate_payment, unallocated_amount
from dinarledger.payments.reconciliation import reconcile

# Convenience alias so external callers can use reconcile_payment()
reconcile_payment = reconcile

__all__ = [
    "allocate_payment",
    "unallocated_amount",
    "reconcile",
    "reconcile_payment",
]
