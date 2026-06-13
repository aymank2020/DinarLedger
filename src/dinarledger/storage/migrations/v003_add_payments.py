"""
Migration v003 — Payments and reconciliation tables.
"""

from __future__ import annotations

import sqlite3
from typing import Any


PAYMENTS_SQL = """
CREATE TABLE IF NOT EXISTS payment (
    payment_id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL,
    amount TEXT NOT NULL,
    status TEXT NOT NULL,
    paid_date TEXT,
    reference TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (invoice_id) REFERENCES invoice(invoice_id)
)
"""

PAYMENTS_INDEX = """
CREATE INDEX IF NOT EXISTS ix_payment_invoice
    ON payment (invoice_id)
"""

RECONCILIATION_SQL = """
CREATE TABLE IF NOT EXISTS reconciliation (
    reconciliation_id TEXT PRIMARY KEY,
    payment_id TEXT NOT NULL,
    expected_amount TEXT NOT NULL,
    actual_amount TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    reconciled_at TEXT,
    notes TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (payment_id) REFERENCES payment(payment_id)
)
"""

RECONCILIATION_INDEX = """
CREATE INDEX IF NOT EXISTS ix_reconciliation_payment
    ON reconciliation (payment_id)
"""


def upgrade(conn: sqlite3.Connection) -> None:
    """Add payments and reconciliation tables."""
    conn.execute(PAYMENTS_SQL)
    conn.execute(PAYMENTS_INDEX)
    conn.execute(RECONCILIATION_SQL)
    conn.execute(RECONCILIATION_INDEX)
