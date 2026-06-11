"""
dinarledger.storage.base — Abstract repository interface and filter primitives.

Defines the generic ``Repository[T]`` ABC that every concrete store must
implement, plus the filtering primitives (``FilterOperator``,
``FilterCondition``) used by the ``find`` method.
"""

from __future__ import annotations

import enum
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Filter primitives
# ---------------------------------------------------------------------------

class FilterOperator(enum.Enum):
    """Operators available for repository filter conditions."""

    EQ = "eq"
    NE = "ne"
    GT = "gt"
    LT = "lt"
    GTE = "gte"
    LTE = "lte"
    IN = "in"
    CONTAINS = "contains"


@dataclass(frozen=True)
class FilterCondition:
    """A single filter predicate to apply against an entity field.

    Attributes
    ----------
    field : str
        Name of the entity attribute to compare.
    operator : FilterOperator
        Comparison operator.
    value : Any
        Value to compare against (or a collection for ``IN`` / ``CONTAINS``).
    """

    field: str
    operator: FilterOperator
    value: Any


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class EntityNotFoundError(Exception):
    """Raised when a repository lookup by ID fails.

    Attributes
    ----------
    entity_type : str
        Human-readable name of the entity type.
    entity_id : str
        The ID that was not found.
    """

    def __init__(self, entity_type: str, entity_id: str) -> None:
        self.entity_type = entity_type
        self.entity_id = entity_id
        super().__init__(
            f"{entity_type} with id '{entity_id}' not found"
        )


# ---------------------------------------------------------------------------
# Abstract repository
# ---------------------------------------------------------------------------

class Repository(ABC, Generic[T]):
    """Generic abstract base class for entity persistence.

    Concrete implementations must support full CRUD plus filtered lookup.
    The type parameter ``T`` represents the domain entity type stored.
    """

    @abstractmethod
    def get(self, id: str) -> T | None:
        """Retrieve an entity by its unique identifier.

        Returns ``None`` when no entity with the given *id* exists.
        """

    @abstractmethod
    def get_all(self) -> list[T]:
        """Return every entity currently stored."""

    @abstractmethod
    def add(self, entity: T) -> T:
        """Persist a new *entity* and return it (possibly with generated ID)."""

    @abstractmethod
    def update(self, entity: T) -> T:
        """Replace the stored version of an entity.

        Raises
        ------
        EntityNotFoundError
            If the entity's ID does not exist in the store.
        """

    @abstractmethod
    def delete(self, id: str) -> bool:
        """Remove an entity by *id*.  Returns ``True`` if something was deleted."""

    @abstractmethod
    def find(self, filter: dict[str, Any] | None = None) -> list[T]:
        """Return entities matching all key/value pairs in *filter*.

        Each key is an entity field name and the corresponding value is
        tested for equality.  To use other operators, pass the result of
        :meth:`_build_conditions` to the concrete implementation.
        """

    # -- Helper for building filter conditions --------------------------------

    @staticmethod
    def _build_conditions(filter: dict[str, Any]) -> list[FilterCondition]:
        """Convert a simple equality dict into a list of :class:`FilterCondition`.

        This is a convenience so callers can pass ``{"status": "active"}``
        rather than constructing :class:`FilterCondition` objects manually.
        """
        return [
            FilterCondition(field=k, operator=FilterOperator.EQ, value=v)
            for k, v in filter.items()
        ]

    # -- Hook for subclasses to apply a single condition -----------------------

    @staticmethod
    def _matches(entity: Any, condition: FilterCondition) -> bool:
        """Evaluate *condition* against *entity* by inspecting attributes.

        Returns ``True`` if the condition is satisfied.
        """
        val = getattr(entity, condition.field, None)
        op = condition.operator
        target = condition.value

        if op == FilterOperator.EQ:
            return val == target
        if op == FilterOperator.NE:
            return val != target
        if op == FilterOperator.GT:
            return val is not None and val > target
        if op == FilterOperator.LT:
            return val is not None and val < target
        if op == FilterOperator.GTE:
            return val is not None and val >= target
        if op == FilterOperator.LTE:
            return val is not None and val <= target
        if op == FilterOperator.IN:
            return val in target
        if op == FilterOperator.CONTAINS:
            return target in val if val is not None else False

        return False  # pragma: no cover
