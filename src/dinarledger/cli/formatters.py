"""Output formatters for the DinarLedger CLI.

Provides consistent formatting across table, JSON, and CSV output modes.
The output format is determined by:

1. The ``--format`` CLI flag (highest priority).
2. The ``OUTPUT_FORMAT`` environment variable.
3. Default: ``table``.
"""

from __future__ import annotations

import csv
import io
import json
import os
from datetime import date
from decimal import Decimal
from typing import Any, Iterable, Sequence

from dinarledger.core.money import Money


# ---------------------------------------------------------------------------
# Format resolution
# ---------------------------------------------------------------------------

def resolve_format(cli_format: str | None = None) -> str:
    """Return the output format string (``table``, ``json``, or ``csv``).

    Priority: *cli_format* > ``OUTPUT_FORMAT`` env var > ``"table"``.
    """
    if cli_format:
        return cli_format.lower()
    env = os.environ.get("OUTPUT_FORMAT", "").lower()
    if env in ("table", "json", "csv"):
        return env
    return "table"


# ---------------------------------------------------------------------------
# Money / Date helpers
# ---------------------------------------------------------------------------

def format_money(money: Money) -> str:
    """Pretty-print a :class:`Money` object as ``"1,234.56 KWD"``."""
    amount = money.amount
    # Format with 2 decimal places and comma separator
    neg = amount < 0
    abs_val = abs(amount)
    int_part = int(abs_val)
    dec_part = abs_val - int_part
    dec_str = f"{dec_part:.2f}"[1:]  # leading ".00"
    int_str = f"{int_part:,}"
    result = f"{int_str}{dec_str} {money.currency}"
    return f"-{result}" if neg else result


def format_date(d: date) -> str:
    """Format a date as ISO-8601 (``YYYY-MM-DD``)."""
    return d.isoformat()


# ---------------------------------------------------------------------------
# Table formatting
# ---------------------------------------------------------------------------

def format_table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    """Render an ASCII table from *headers* and *rows*.

    Column widths are auto-sized. Values are converted to strings via
    :func:`str` unless they are :class:`Money` or :class:`date` instances,
    which use :func:`format_money` / :func:`format_date`.
    """
    str_rows = [[_cell_str(c) for c in row] for row in rows]
    str_headers = list(headers)

    # Compute column widths
    col_count = len(str_headers)
    widths = [0] * col_count
    for i, h in enumerate(str_headers):
        widths[i] = max(widths[i], len(h))
    for row in str_rows:
        for i, cell in enumerate(row):
            if i < col_count:
                widths[i] = max(widths[i], len(cell))

    # Build separator
    sep = "+" + "+".join("-" * (w + 2) for w in widths) + "+"
    # Build header line
    header_line = "|" + "|".join(
        f" {h:<{widths[i]}} " for i, h in enumerate(str_headers)
    ) + "|"

    lines = [sep, header_line, sep]
    for row in str_rows:
        line = "|" + "|".join(
            f" {row[i]:<{widths[i]}} " if i < col_count else ""
            for i in range(col_count)
        ) + "|"
        lines.append(line)
    lines.append(sep)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# JSON formatting
# ---------------------------------------------------------------------------

def format_json(data: Any) -> str:
    """Serialize *data* as indented JSON.

    Handles :class:`Money`, :class:`date`, and :class:`Decimal` objects.
    """
    return json.dumps(data, indent=2, default=_json_default)


def _json_default(obj: Any) -> Any:
    if isinstance(obj, Money):
        return {"amount": str(obj.amount), "currency": obj.currency}
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return str(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


# ---------------------------------------------------------------------------
# CSV formatting
# ---------------------------------------------------------------------------

def format_csv(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    """Render *headers* and *rows* as CSV."""
    buf = io.StringIO(newline="")
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(headers)
    for row in rows:
        writer.writerow([_cell_str(c) for c in row])
    return buf.getvalue().rstrip("\n")


# ---------------------------------------------------------------------------
# Dispatch helper
# ---------------------------------------------------------------------------

def output(
    data: Any,
    headers: Sequence[str] | None = None,
    rows: Sequence[Sequence[Any]] | None = None,
    fmt: str = "table",
) -> str:
    """Format *data* according to *fmt*.

    For table/csv, *headers* and *rows* may be provided explicitly.
    When a dict is passed without headers/rows and fmt is table or csv,
    it is rendered as a key-value table (Field | Value).
    For json, *data* is serialised directly.
    """
    if fmt == "json":
        return format_json(data)

    # Auto-generate headers/rows from a single dict
    if (headers is None or rows is None) and isinstance(data, dict):
        headers = ["Field", "Value"]
        rows = [[k, v] for k, v in data.items()]

    if headers is None or rows is None:
        # Fallback to JSON when tabular data is unavailable
        return format_json(data)

    if fmt == "csv":
        return format_csv(headers, rows)

    return format_table(headers, rows)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _cell_str(value: Any) -> str:
    """Convert a cell value to its display string."""
    if isinstance(value, Money):
        return format_money(value)
    if isinstance(value, date):
        return format_date(value)
    return str(value)
