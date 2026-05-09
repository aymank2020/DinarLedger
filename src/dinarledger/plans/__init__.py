"""
Plan management package for DinarLedger.

This package provides proration and upgrade/downgrade credit calculations
for plan changes mid-cycle.

Re-exports
----------
prorate
    Alias for :func:`dinarledger.plans.proration.prorate`.
calculate_credit
    Alias for :func:`dinarledger.plans.proration.calculate_upgrade_credit`.
"""

from dinarledger.plans.proration import prorate, calculate_upgrade_credit as calculate_credit

__all__ = ["prorate", "calculate_credit"]
