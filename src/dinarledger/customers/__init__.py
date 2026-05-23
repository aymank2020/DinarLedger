"""
Customer management package for DinarLedger.

This package provides credit-limit checking and customer-ledger (accounts
receivable) functionality.

Re-exports
----------
credit_limit_check
    Alias for :func:`dinarledger.customers.credit.check_credit_limit`.
customer_ledger_balance
    Alias for :func:`dinarledger.customers.ledger.customer_ledger_balance`.
"""

from dinarledger.customers.credit import check_credit_limit as credit_limit_check
from dinarledger.customers.ledger import customer_ledger_balance

__all__ = ["credit_limit_check", "customer_ledger_balance"]
