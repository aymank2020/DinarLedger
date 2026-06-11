"""
dinarledger.storage.memory — Thread-safe in-memory repository for testing.

Stores entities in a plain ``dict`` protected by a ``threading.Lock``.
Auto-generates UUID-based IDs when the entity has no ``id``-like attribute
or the attribute is ``None``.
"""

from __future__ import annotations

import threading
import uuid
from typing import Any, Generic, TypeVar

from .base import EntityNotFoundError, FilterCondition, FilterOperator, Repository

T = TypeVar("T")

# Common attribute names that serve as the primary key.
_ID_ATTRS = ("id", "plan_id", "sub_id", "invoice_id", "payment_id", "customer_id", "code")


def _entity_id(entity: Any) -> str | None:
    """Return the primary-key value from *entity*, or ``None``."""
    for attr in _ID_ATTRS:
        val = getattr(entity, attr, None)
        if val is not None:
            return str(val)
    return None


def _set_entity_id(entity: Any, new_id: str) -> None:
    """Set the primary-key value on *entity* (frozen dataclass aware)."""
    for attr in _ID_ATTRS:
        if hasattr(entity, attr):
            # Frozen dataclass — use object.__setattr__
            try:
                object.__setattr__(entity, attr, new_id)
            except AttributeError:
                # Some frozen dataclasses may not allow this; best-effort.
                pass
            return


class MemoryRepository(Repository, Generic[T]):
    """In-memory :class:`Repository` backed by a dict.

    Parameters
    ----------
    entity_type : type[T]
        The concrete entity class (used for error messages and ID discovery).
    """

    def __init__(self, entity_type: type[T]) -> None:
        self._entity_type = entity_type
        self._store: dict[str, T] = {}
        self._lock = threading.Lock()

    # -- CRUD -----------------------------------------------------------------

    def get(self, id: str) -> T | None:  # noqa: A002
        with self._lock:
            return self._store.get(id)

    def get_all(self) -> list[T]:
        with self._lock:
            return list(self._store.values())

    def add(self, entity: T) -> T:
        with self._lock:
            eid = _entity_id(entity)
            if eid is None:
                eid = uuid.uuid4().hex[:12]
                _set_entity_id(entity, eid)
            self._store[eid] = entity
            return entity

    def update(self, entity: T) -> T:
        with self._lock:
            eid = _entity_id(entity)
            if eid is None or eid not in self._store:
                raise EntityNotFoundError(
                    self._entity_type.__name__, eid or "<unknown>"
                )
            self._store[eid] = entity
            return entity

    def delete(self, id: str) -> bool:  # noqa: A002
        with self._lock:
            if id in self._store:
                del self._store[id]
                return True
            return False

    # -- Filtering ------------------------------------------------------------

    def find(self, filter: dict[str, Any] | None = None) -> list[T]:  # noqa: A002
        if not filter:
            return self.get_all()

        conditions = self._build_conditions(filter)
        with self._lock:
            return [
                entity
                for entity in self._store.values()
                if all(self._matches(entity, c) for c in conditions)
            ]

    def find_with_conditions(self, conditions: list[FilterCondition]) -> list[T]:
        """Advanced find using explicit :class:`FilterCondition` objects."""
        with self._lock:
            return [
                entity
                for entity in self._store.values()
                if all(self._matches(entity, c) for c in conditions)
            ]

    # -- Utility --------------------------------------------------------------

    def count(self) -> int:
        """Return the number of stored entities."""
        with self._lock:
            return len(self._store)

    def clear(self) -> None:
        """Remove all entities (useful between tests)."""
        with self._lock:
            self._store.clear()
