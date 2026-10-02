"""DinarLedger reports — aging, MRR, and deferred-revenue waterfall.

Re-exports the public report functions and dataclasses so consumers
can ``from dinarledger.reports import aging_report`` etc.
"""

from dinarledger.reports.aging import AgingBucket, aging_report
from dinarledger.reports.deferred_schedule import WaterfallEntry, deferred_waterfall
from dinarledger.reports.mrr import MRRBreakdown, calculate_mrr

__all__ = [
    "AgingBucket",
    "aging_report",
    "MRRBreakdown",
    "calculate_mrr",
    "WaterfallEntry",
    "deferred_waterfall",
]
