"""
Migration v002 — Add FX rates table.
"""

from __future__ import annotations

import sqlite3
from typing import Any


FX_RATES_SQL = """
CREATE TABLE IF NOT EXISTS fxrate (
    base TEXT NOT NULL,
    quote TEXT NOT NULL,
    rate TEXT NOT NULL,
    rate_date TEXT NOT NULL,
    PRIMARY KEY (base, quote, rate_date)
)
"""

FX_RATES_INDEX = """
CREATE INDEX IF NOT EXISTS ix_fxrate_pair_date
    ON fxrate (base, quote, rate_date)
"""


def upgrade(conn: sqlite3.Connection) -> None:
    """Add the fxrate table and index."""
    conn.execute(FX_RATES_SQL)
    conn.execute(FX_RATES_INDEX)
