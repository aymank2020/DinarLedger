"""Foreign exchange (FX) module — rate management and currency conversion.

Re-exports:

- :func:`convert` — convert a :class:`Money` amount to a target currency
- :func:`revalue` — revalue AR invoices for unrealized FX gains/losses
"""

from dinarledger.fx.rates import FXRate, convert, cross_rate
from dinarledger.fx.revaluation import unrealized_gain, revalue_ar

# Public alias expected by the package-level import
revalue = revalue_ar

__all__ = [
    "FXRate",
    "convert",
    "cross_rate",
    "unrealized_gain",
    "revalue",
    "revalue_ar",
]
