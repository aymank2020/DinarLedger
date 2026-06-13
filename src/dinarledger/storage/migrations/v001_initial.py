"""
Migration v001 — Initial schema: customers, plans, subscriptions tables.
"""

from __future__ import annotations

import sqlite3
from typing import Any


CUSTOMERS_SQL = """
CREATE TABLE IF NOT EXISTS customer (
    customer_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    currency TEXT NOT NULL,
    credit_limit TEXT,
    tax_exempt INTEGER NOT NULL DEFAULT 0,
    tax_jurisdiction TEXT NOT NULL DEFAULT ''
)
"""

PLANS_SQL = """
CREATE TABLE IF NOT EXISTS plan (
    plan_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    base_price TEXT NOT NULL,
    billing_cycle TEXT NOT NULL,
    setup_fee TEXT,
    trial_days INTEGER NOT NULL DEFAULT 0,
    tax_code TEXT NOT NULL DEFAULT '',
    seats_included INTEGER NOT NULL DEFAULT 1
)
"""

SUBSCRIPTIONS_SQL = """
CREATE TABLE IF NOT EXISTS subscription (
    sub_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    plan TEXT NOT NULL,
    status TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT,
    seat_count INTEGER NOT NULL DEFAULT 1,
    cancelled_at TEXT,
    current_period_start TEXT,
    current_period_end TEXT,
    trial_ends_at TEXT,
    FOREIGN KEY (customer_id) REFERENCES customer(customer_id)
)
"""


def upgrade(conn: sqlite3.Connection) -> None:
    """Apply the initial schema migration."""
    conn.execute(CUSTOMERS_SQL)
    conn.execute(PLANS_SQL)
    conn.execute(SUBSCRIPTIONS_SQL)
