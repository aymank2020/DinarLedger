"""
Subscription management package for DinarLedger.

This package handles subscription lifecycle (trial → active → cancelled)
and per-seat pricing adjustments.

Re-exports
----------
subscribe
    Alias for :func:`dinarledger.subscriptions.lifecycle.subscribe`.
change_plan
    Alias for :func:`dinarledger.subscriptions.lifecycle.change_plan`.
cancel_subscription
    Alias for :func:`dinarledger.subscriptions.lifecycle.cancel_subscription`.
"""

from dinarledger.subscriptions.lifecycle import subscribe, change_plan, cancel_subscription

__all__ = ["subscribe", "change_plan", "cancel_subscription"]
