"""
Billing package for DinarLedger.

This package handles invoice generation, adjustments, and voiding.

Re-exports
----------
generate_invoice
    Alias for :func:`dinarledger.billing.invoice_gen.generate_invoice`.
apply_adjustment
    Alias for :func:`dinarledger.billing.invoice_gen.apply_adjustment`.
"""

from dinarledger.billing.invoice_gen import generate_invoice, apply_adjustment

__all__ = ["generate_invoice", "apply_adjustment"]
