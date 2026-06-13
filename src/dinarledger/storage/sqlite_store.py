"""
dinarledger.storage.sqlite_store — SQLite-backed repository.

Provides full CRUD with parameterized queries, automatic schema creation
from entity type hints, and transaction support (begin / commit / rollback).
"""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any, Generator, Generic, Type, TypeVar, get_args, get_origin, get_type_hints

from .base import EntityNotFoundError, FilterCondition, FilterOperator, Repository
from .serializers import EntitySerializer

T = TypeVar("T")

# ---------------------------------------------------------------------------
# Type mapping helpers
# ---------------------------------------------------------------------------

_TYPE_TO_SQL: dict[type, str] = {
    str: "TEXT",
    int: "INTEGER",
    float: "REAL",
    bool: "INTEGER",
    Decimal: "TEXT",
    date: "TEXT",
}


def _python_type_to_sql(py_type: type) -> str:
    """Map a Python type hint to a SQLite column type."""
    if py_type in _TYPE_TO_SQL:
        return _TYPE_TO_SQL[py_type]

    origin = get_origin(py_type)
    if origin is list:
        return "TEXT"  # JSON-serialized

    # Enums
    if isinstance(py_type, type) and issubclass(py_type, Enum):
        return "TEXT"

    # Money → store as TEXT (JSON)
    from dinarledger.core.money import Money
    if isinstance(py_type, type) and issubclass(py_type, Money):
        return "TEXT"

    # Default — anything else goes as TEXT
    return "TEXT"


def _is_optional(tp: Any) -> bool:
    """Return True if *tp* is Optional[X] (i.e. Union[X, None])."""
    args = get_args(tp)
    return type(None) in args


def _unwrap_optional(tp: Any) -> Any:
    """Strip NoneType from Optional[X], returning X."""
    args = get_args(tp)
    return next(a for a in args if a is not type(None))


def _extract_id_field(entity_type: type) -> str:
    """Determine the primary-key field name for *entity_type*."""
    candidates = [
        "id", "plan_id", "sub_id", "invoice_id",
        "payment_id", "customer_id", "code",
    ]
    hints = get_type_hints(entity_type)
    for c in candidates:
        if c in hints:
            return c
    return "id"


# ---------------------------------------------------------------------------
# Schema builder
# ---------------------------------------------------------------------------

def _build_create_table_sql(entity_type: type, table_name: str) -> str:
    """Generate a CREATE TABLE statement from a dataclass type."""
    pk_field = _extract_id_field(entity_type)
    columns: list[str] = []

    hints = get_type_hints(entity_type)
    if not hasattr(entity_type, "__dataclass_fields__"):
        raise TypeError(f"{entity_type} is not a dataclass")

    for field_name in entity_type.__dataclass_fields__:
        py_type = hints.get(field_name, str)
        nullable = _is_optional(py_type)
        if nullable:
            py_type = _unwrap_optional(py_type)

        sql_type = _python_type_to_sql(py_type)
        col_def = f"{field_name} {sql_type}"

        if field_name == pk_field:
            col_def += " PRIMARY KEY"

        columns.append(col_def)

    return f"CREATE TABLE IF NOT EXISTS {table_name} (\n  " + ",\n  ".join(columns) + "\n)"


# ---------------------------------------------------------------------------
# Value converters for SQLite
# ---------------------------------------------------------------------------

def _to_sql_value(entity: Any, field_name: str) -> Any:
    """Convert a field value from a domain entity to a SQLite-compatible value."""
    val = getattr(entity, field_name, None)
    if val is None:
        return None
    if isinstance(val, bool):
        return int(val)
    if isinstance(val, Decimal):
        return str(val)
    if isinstance(val, date):
        return val.isoformat()
    if isinstance(val, Enum):
        return val.value
    from dinarledger.core.money import Money
    if isinstance(val, Money):
        return json.dumps(EntitySerializer.serialize(val))
    if isinstance(val, (list, tuple)):
        return json.dumps([EntitySerializer.serialize(item) for item in val])
    # Nested dataclass
    if hasattr(val, "__dataclass_fields__"):
        return json.dumps(EntitySerializer.serialize(val))
    return val


def _from_sql_value(val: Any, py_type: Any) -> Any:
    """Convert a SQLite value back to the Python type."""
    if val is None:
        return None

    if py_type is str:
        return val
    if py_type is int:
        return int(val)
    if py_type is float:
        return float(val)
    if py_type is bool:
        # SQLite stores bools as 0/1
        return bool(int(val))
    if py_type is Decimal:
        return Decimal(str(val))
    if py_type is date:
        return date.fromisoformat(val)
    if isinstance(py_type, type) and issubclass(py_type, Enum):
        return py_type(val)
    from dinarledger.core.money import Money
    if py_type is Money:
        return EntitySerializer.deserialize(json.loads(val))
    # List types
    origin = get_origin(py_type)
    if origin is list:
        items = json.loads(val)
        return [EntitySerializer.deserialize(item) for item in items]
    # Nested dataclass
    if isinstance(py_type, type) and hasattr(py_type, "__dataclass_fields__"):
        return EntitySerializer.deserialize(json.loads(val))

    return val


# ---------------------------------------------------------------------------
# SqliteRepository
# ---------------------------------------------------------------------------

class SqliteRepository(Repository, Generic[T]):
    """SQLite-backed :class:`Repository` with full CRUD and transactions.

    Parameters
    ----------
    entity_type : type[T]
        The dataclass type of the entity.
    db_path : str | Path
        Path to the SQLite database file.
    table_name : str | None
        Override the table name (defaults to entity class name lowercase).
    """

    def __init__(
        self,
        entity_type: type[T],
        db_path: str | Path,
        table_name: str | None = None,
    ) -> None:
        self._entity_type = entity_type
        self._db_path = Path(db_path)
        self._table_name = table_name or entity_type.__name__.lower()
        self._pk_field = _extract_id_field(entity_type)
        self._local = threading.local()  # per-thread connection
        self._in_transaction = threading.local()

        # Ensure the DB directory exists and schema is ready
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    # -- Connection management ------------------------------------------------

    @contextmanager
    def _connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Provide a database connection (one per thread)."""
        conn: sqlite3.Connection | None = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(str(self._db_path))
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            self._local.conn = conn
        try:
            yield conn
        except Exception:
            # Only rollback if we are NOT inside an explicit transaction
            # (the transaction context manager handles its own rollback)
            in_txn = getattr(self._in_transaction, "active", False)
            if not in_txn:
                conn.rollback()
            raise

    def _auto_commit(self, conn: sqlite3.Connection) -> None:
        """Commit only if we are NOT inside an explicit transaction."""
        in_txn = getattr(self._in_transaction, "active", False)
        if not in_txn:
            conn.commit()

    def close(self) -> None:
        """Close the thread-local connection if open."""
        conn: sqlite3.Connection | None = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None

    # -- Schema management ----------------------------------------------------

    def _ensure_schema(self) -> None:
        """Create the table if it doesn't exist."""
        sql = _build_create_table_sql(self._entity_type, self._table_name)
        with self._connection() as conn:
            conn.execute(sql)
            conn.commit()

    # -- CRUD -----------------------------------------------------------------

    def get(self, id: str) -> T | None:  # noqa: A002
        with self._connection() as conn:
            cursor = conn.execute(
                f"SELECT * FROM {self._table_name} WHERE {self._pk_field} = ?",
                (id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return self._row_to_entity(row, cursor.description)

    def get_all(self) -> list[T]:
        with self._connection() as conn:
            cursor = conn.execute(f"SELECT * FROM {self._table_name}")
            rows = cursor.fetchall()
            return [self._row_to_entity(row, cursor.description) for row in rows]

    def add(self, entity: T) -> T:
        fields = list(self._entity_type.__dataclass_fields__.keys())
        values = [_to_sql_value(entity, f) for f in fields]
        placeholders = ", ".join("?" for _ in fields)
        col_names = ", ".join(fields)

        with self._connection() as conn:
            conn.execute(
                f"INSERT INTO {self._table_name} ({col_names}) VALUES ({placeholders})",
                values,
            )
            self._auto_commit(conn)
        return entity

    def update(self, entity: T) -> T:
        fields = list(self._entity_type.__dataclass_fields__.keys())
        set_clause = ", ".join(f"{f} = ?" for f in fields if f != self._pk_field)
        values = [_to_sql_value(entity, f) for f in fields if f != self._pk_field]
        pk_value = _to_sql_value(entity, self._pk_field)

        with self._connection() as conn:
            cursor = conn.execute(
                f"UPDATE {self._table_name} SET {set_clause} WHERE {self._pk_field} = ?",
                values + [pk_value],
            )
            if cursor.rowcount == 0:
                raise EntityNotFoundError(
                    self._entity_type.__name__, str(pk_value)
                )
            self._auto_commit(conn)
        return entity

    def delete(self, id: str) -> bool:  # noqa: A002
        with self._connection() as conn:
            cursor = conn.execute(
                f"DELETE FROM {self._table_name} WHERE {self._pk_field} = ?",
                (id,),
            )
            self._auto_commit(conn)
            return cursor.rowcount > 0

    # -- Filtering ------------------------------------------------------------

    def find(self, filter: dict[str, Any] | None = None) -> list[T]:  # noqa: A002
        if not filter:
            return self.get_all()

        conditions = []
        params: list[Any] = []
        for key, value in filter.items():
            conditions.append(f"{key} = ?")
            if isinstance(value, Enum):
                params.append(value.value)
            elif isinstance(value, Decimal):
                params.append(str(value))
            elif isinstance(value, date):
                params.append(value.isoformat())
            else:
                params.append(value)

        where_clause = " AND ".join(conditions)
        with self._connection() as conn:
            cursor = conn.execute(
                f"SELECT * FROM {self._table_name} WHERE {where_clause}",
                params,
            )
            rows = cursor.fetchall()
            return [self._row_to_entity(row, cursor.description) for row in rows]

    def find_with_conditions(self, conditions: list[FilterCondition]) -> list[T]:
        """Advanced find using explicit :class:`FilterCondition` objects."""
        where_parts: list[str] = []
        params: list[Any] = []

        op_map = {
            FilterOperator.EQ: "=",
            FilterOperator.NE: "!=",
            FilterOperator.GT: ">",
            FilterOperator.LT: "<",
            FilterOperator.GTE: ">=",
            FilterOperator.LTE: "<=",
        }

        for cond in conditions:
            if cond.operator in op_map:
                where_parts.append(f"{cond.field} {op_map[cond.operator]} ?")
                val = cond.value
                if isinstance(val, Enum):
                    val = val.value
                elif isinstance(val, Decimal):
                    val = str(val)
                elif isinstance(val, date):
                    val = val.isoformat()
                params.append(val)
            elif cond.operator == FilterOperator.IN:
                placeholders = ", ".join("?" for _ in cond.value)
                where_parts.append(f"{cond.field} IN ({placeholders})")
                for v in cond.value:
                    if isinstance(v, Enum):
                        params.append(v.value)
                    else:
                        params.append(v)
            elif cond.operator == FilterOperator.CONTAINS:
                where_parts.append(f"{cond.field} LIKE ?")
                params.append(f"%{cond.value}%")

        where_clause = " AND ".join(where_parts) if where_parts else "1=1"
        with self._connection() as conn:
            cursor = conn.execute(
                f"SELECT * FROM {self._table_name} WHERE {where_clause}",
                params,
            )
            rows = cursor.fetchall()
            return [self._row_to_entity(row, cursor.description) for row in rows]

    # -- Transaction support --------------------------------------------------

    def begin(self) -> None:
        """Begin an explicit transaction."""
        self._in_transaction.active = True
        with self._connection() as conn:
            conn.execute("BEGIN")

    def commit(self) -> None:
        """Commit the current transaction."""
        with self._connection() as conn:
            conn.commit()
        self._in_transaction.active = False

    def rollback(self) -> None:
        """Roll back the current transaction."""
        with self._connection() as conn:
            conn.rollback()
        self._in_transaction.active = False

    @contextmanager
    def transaction(self) -> Generator[None, None, None]:
        """Context manager for a transaction — auto-commits or rolls back."""
        self._in_transaction.active = True
        with self._connection() as conn:
            try:
                yield
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                self._in_transaction.active = False

    # -- Row → Entity conversion ----------------------------------------------

    def _row_to_entity(self, row: tuple, description: Any) -> T:
        """Convert a database row to a domain entity."""
        col_names = [desc[0] for desc in description]
        kwargs: dict[str, Any] = {}
        hints = get_type_hints(self._entity_type)

        for col_name, value in zip(col_names, row):
            if col_name not in self._entity_type.__dataclass_fields__:
                continue
            py_type = hints.get(col_name, str)
            nullable = _is_optional(py_type)
            if nullable:
                py_type = _unwrap_optional(py_type)
            kwargs[col_name] = _from_sql_value(value, py_type)

        return self._entity_type(**kwargs)

    # -- Utility --------------------------------------------------------------

    def count(self) -> int:
        with self._connection() as conn:
            cursor = conn.execute(f"SELECT COUNT(*) FROM {self._table_name}")
            return cursor.fetchone()[0]
