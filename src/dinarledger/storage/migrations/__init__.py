"""
dinarledger.storage.migrations — Database schema migration runner.

Provides a simple forward-only migration system. Each migration module
must expose a ``upgrade(db_path)`` callable. The runner tracks applied
migrations in a ``_migrations`` table.
"""

from __future__ import annotations

import importlib
import sqlite3
from pathlib import Path
from typing import Any


_MIGRATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS _migrations (
    version TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
)
"""


def _get_applied(conn: sqlite3.Connection) -> set[str]:
    """Return the set of already-applied migration version strings."""
    conn.execute(_MIGRATIONS_TABLE)
    rows = conn.execute("SELECT version FROM _migrations").fetchall()
    return {row[0] for row in rows}


def run_migrations(db_path: str | Path, migrations_package: str = __package__) -> list[str]:
    """Run all pending migrations for the database at *db_path*.

    Parameters
    ----------
    db_path : str | Path
        Path to the SQLite database.
    migrations_package : str
        Dot-path of the package containing migration modules.

    Returns
    -------
    list[str]
        Version strings of newly applied migrations.
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    applied = _get_applied(conn)
    newly_applied: list[str] = []

    # Discover migration modules (vNNN_*.py)
    pkg_dir = Path(__file__).parent
    migration_files = sorted(pkg_dir.glob("v*_*.py"))

    for mf in migration_files:
        version = mf.stem  # e.g. "v001_initial"
        if version in applied:
            continue

        module_name = f"{migrations_package}.{version}"
        mod = importlib.import_module(module_name)
        mod.upgrade(conn)  # type: ignore[attr-defined]

        conn.execute(
            "INSERT INTO _migrations (version) VALUES (?)",
            (version,),
        )
        conn.commit()
        newly_applied.append(version)

    conn.close()
    return newly_applied
