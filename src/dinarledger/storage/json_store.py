"""
dinarledger.storage.json_store — File-backed JSON repository.

Persists entities to a JSON file using atomic writes (write-to-temp + rename)
and optional file locking.  Supports lazy loading and auto-save on mutation.
"""

from __future__ import annotations

import fcntl
import json
import os
import platform
import shutil
import tempfile
import threading
import uuid
from pathlib import Path
from typing import Any, Generic, TypeVar

from .base import EntityNotFoundError, Repository
from .serializers import EntitySerializer, register_entity

T = TypeVar("T")

# On Windows we cannot use fcntl; fall back to no-op locking.
_IS_WINDOWS = platform.system() == "Windows"


def _entity_id(entity: Any) -> str | None:
    """Return the primary-key value from *entity*, or ``None``."""
    for attr in ("id", "plan_id", "sub_id", "invoice_id", "payment_id", "customer_id", "code"):
        val = getattr(entity, attr, None)
        if val is not None:
            return str(val)
    return None


def _set_entity_id(entity: Any, new_id: str) -> None:
    for attr in ("id", "plan_id", "sub_id", "invoice_id", "payment_id", "customer_id", "code"):
        if hasattr(entity, attr):
            try:
                object.__setattr__(entity, attr, new_id)
            except AttributeError:
                pass
            return


class _FileLock:
    """Cross-platform advisory file lock (best-effort on Windows)."""

    def __init__(self, path: Path) -> None:
        self._lock_path = path.with_suffix(path.suffix + ".lock")
        self._fd: int | None = None

    def __enter__(self) -> "_FileLock":
        if _IS_WINDOWS:
            return self
        self._fd = os.open(str(self._lock_path), os.O_CREAT | os.O_RDWR)
        fcntl.flock(self._fd, fcntl.LOCK_EX)
        return self

    def __exit__(self, *args: Any) -> None:
        if self._fd is not None:
            fcntl.flock(self._fd, fcntl.LOCK_UN)
            os.close(self._fd)
            self._fd = None


class JsonRepository(Repository, Generic[T]):
    """File-backed :class:`Repository` that persists to a JSON file.

    Parameters
    ----------
    entity_type : type[T]
        The concrete entity class.
    file_path : str | Path
        Path to the JSON file.
    backup_count : int
        Number of rotating backups to keep (0 = no backups).
    auto_save : bool
        If ``True`` (default), every mutation immediately writes to disk.
    """

    def __init__(
        self,
        entity_type: type[T],
        file_path: str | Path,
        backup_count: int = 3,
        auto_save: bool = True,
    ) -> None:
        self._entity_type = entity_type
        self._file_path = Path(file_path)
        self._backup_count = backup_count
        self._auto_save = auto_save
        self._lock = threading.Lock()
        self._store: dict[str, T] | None = None  # None => not loaded yet
        # Register the entity type so deserialization can reconstruct it
        if hasattr(entity_type, "__dataclass_fields__"):
            register_entity(entity_type)

    # -- Internal persistence -------------------------------------------------

    def _ensure_loaded(self) -> None:
        """Load data from disk on first access (lazy loading)."""
        if self._store is not None:
            return
        with self._lock:
            if self._store is not None:
                return
            if self._file_path.exists():
                with _FileLock(self._file_path):
                    raw = self._file_path.read_text(encoding="utf-8")
                data = json.loads(raw)
                self._store = {}
                for key, value in data.items():
                    self._store[key] = EntitySerializer.deserialize(value)
            else:
                self._store = {}

    def _save(self) -> None:
        """Write current store to disk atomically."""
        if self._store is None:
            return

        serialized = {
            key: EntitySerializer.serialize(entity)
            for key, entity in self._store.items()
        }
        raw = json.dumps(serialized, indent=2, ensure_ascii=False)

        # Atomic write: write to temp file then rename
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            dir=str(self._file_path.parent),
            suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(raw)
            # Rotate backups
            if self._backup_count > 0 and self._file_path.exists():
                self._rotate_backups()
            os.replace(tmp_path, str(self._file_path))
        except BaseException:
            # Clean up temp file on error
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def _rotate_backups(self) -> None:
        """Rotate backup files: .bak.3 <- .bak.2 <- .bak.1 <- current."""
        for i in range(self._backup_count, 1, -1):
            src = self._file_path.with_suffix(f".bak.{i - 1}")
            dst = self._file_path.with_suffix(f".bak.{i}")
            if src.exists():
                shutil.copy2(str(src), str(dst))
        shutil.copy2(str(self._file_path), str(self._file_path.with_suffix(".bak.1")))

    # -- CRUD -----------------------------------------------------------------

    def get(self, id: str) -> T | None:  # noqa: A002
        self._ensure_loaded()
        assert self._store is not None
        return self._store.get(id)

    def get_all(self) -> list[T]:
        self._ensure_loaded()
        assert self._store is not None
        return list(self._store.values())

    def add(self, entity: T) -> T:
        self._ensure_loaded()
        assert self._store is not None
        with self._lock:
            eid = _entity_id(entity)
            if eid is None:
                eid = uuid.uuid4().hex[:12]
                _set_entity_id(entity, eid)
            self._store[eid] = entity
            if self._auto_save:
                self._save()
            return entity

    def update(self, entity: T) -> T:
        self._ensure_loaded()
        assert self._store is not None
        with self._lock:
            eid = _entity_id(entity)
            if eid is None or eid not in self._store:
                raise EntityNotFoundError(
                    self._entity_type.__name__, eid or "<unknown>"
                )
            self._store[eid] = entity
            if self._auto_save:
                self._save()
            return entity

    def delete(self, id: str) -> bool:  # noqa: A002
        self._ensure_loaded()
        assert self._store is not None
        with self._lock:
            if id not in self._store:
                return False
            del self._store[id]
            if self._auto_save:
                self._save()
            return True

    # -- Filtering ------------------------------------------------------------

    def find(self, filter: dict[str, Any] | None = None) -> list[T]:  # noqa: A002
        self._ensure_loaded()
        assert self._store is not None
        if not filter:
            return self.get_all()
        conditions = self._build_conditions(filter)
        with self._lock:
            return [
                entity
                for entity in self._store.values()
                if all(self._matches(entity, c) for c in conditions)
            ]

    # -- Utility --------------------------------------------------------------

    def count(self) -> int:
        self._ensure_loaded()
        assert self._store is not None
        return len(self._store)

    def flush(self) -> None:
        """Force a write to disk even if auto_save is disabled."""
        self._save()

    def reload(self) -> None:
        """Discard in-memory cache and force reload from disk."""
        with self._lock:
            self._store = None
