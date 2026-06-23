"""
dinarledger.utils.slug — Slug and ID generation utilities.

Provides URL-safe slug creation, prefixed unique IDs, and formatted
invoice numbers.
"""

from __future__ import annotations

import re
import uuid
from datetime import date
from typing import Optional


def slugify(text: str) -> str:
    """Convert *text* to a URL-safe slug.

    Lowercases the input, replaces non-alphanumeric runs with hyphens,
    and strips leading/trailing hyphens.

    Parameters
    ----------
    text : str
        The input string.

    Returns
    -------
    str
        The slugified string.

    Examples
    --------
    >>> slugify("Pro Monthly Plan")
    'pro-monthly-plan'
    >>> slugify("  Hello, World!  ")
    'hello-world'
    """
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = text.strip("-")
    return text


def generate_id(prefix: Optional[str] = None) -> str:
    """Generate a unique ID with an optional *prefix*.

    Uses :func:`uuid.uuid4` for uniqueness.  The prefix, if provided,
    is separated from the UUID by a hyphen.

    Parameters
    ----------
    prefix : str or None, optional
        A short prefix such as ``"cust"`` or ``"sub"``.

    Returns
    -------
    str
        A unique identifier, e.g. ``"cust-a1b2c3d4e5f6"``.

    Examples
    --------
    >>> len(generate_id("plan").split("-")[1])
    12
    """
    uid = uuid.uuid4().hex[:12]
    if prefix:
        return f"{prefix}-{uid}"
    return uid


def generate_invoice_number() -> str:
    """Generate a formatted invoice number.

    Format: ``INV-YYYYMMDD-XXXX`` where ``YYYYMMDD`` is today's date
    and ``XXXX`` is a 4-character hex segment from a UUID.

    Returns
    -------
    str
        An invoice number such as ``"INV-20260115-a1b2"``.
    """
    today = date.today().strftime("%Y%m%d")
    short_uid = uuid.uuid4().hex[:4]
    return f"INV-{today}-{short_uid}"
