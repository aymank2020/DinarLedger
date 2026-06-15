"""Tests for the migration runner.

Covers forward migration, idempotency, and version tracking.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from dinarledger.storage.migrations import run_migrations


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "migrations_test.db"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestMigrations:
    def test_initial_run_creates_tables(self, db_path: Path) -> None:
        applied = run_migrations(db_path)
        assert len(applied) >= 3
        # v001 should create customer, plan, subscription tables
        conn = sqlite3.connect(str(db_path))
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        conn.close()
        assert "customer" in tables
        assert "plan" in tables
        assert "subscription" in tables

    def test_v002_creates_fxrate_table(self, db_path: Path) -> None:
        run_migrations(db_path)
        conn = sqlite3.connect(str(db_path))
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        conn.close()
        assert "fxrate" in tables

    def test_v003_creates_payment_tables(self, db_path: Path) -> None:
        run_migrations(db_path)
        conn = sqlite3.connect(str(db_path))
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        conn.close()
        assert "payment" in tables
        assert "reconciliation" in tables

    def test_idempotent(self, db_path: Path) -> None:
        """Running migrations twice should not re-apply."""
        first = run_migrations(db_path)
        second = run_migrations(db_path)
        assert len(first) >= 3
        assert len(second) == 0

    def test_versions_are_tracked(self, db_path: Path) -> None:
        run_migrations(db_path)
        conn = sqlite3.connect(str(db_path))
        rows = conn.execute("SELECT version FROM _migrations ORDER BY version").fetchall()
        conn.close()
        versions = [row[0] for row in rows]
        assert "v001_initial" in versions
        assert "v002_add_fx_rates" in versions
        assert "v003_add_payments" in versions
