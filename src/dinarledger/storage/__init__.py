"""
dinarledger.storage — Persistence layer for DinarLedger.

Public API
----------
Repository         Abstract base class for entity repositories.
MemoryRepository   Thread-safe in-memory store (ideal for testing).
JsonRepository     File-backed JSON store with atomic writes.
SqliteRepository   SQLite-backed store with transaction support.
UnitOfWork         Transaction wrapper for grouped operations.

FilterOperator     Enum of comparison operators for queries.
FilterCondition    Structured filter predicate.
EntityNotFoundError  Raised when an entity lookup fails.
EntitySerializer   Round-trip serializer for domain types.
"""

from .base import EntityNotFoundError, FilterCondition, FilterOperator, Repository
from .json_store import JsonRepository
from .memory import MemoryRepository
from .serializers import EntitySerializer
from .sqlite_store import SqliteRepository
from .unit_of_work import UnitOfWork

__all__ = [
    "Repository",
    "MemoryRepository",
    "JsonRepository",
    "SqliteRepository",
    "UnitOfWork",
    "FilterOperator",
    "FilterCondition",
    "EntityNotFoundError",
    "EntitySerializer",
]
