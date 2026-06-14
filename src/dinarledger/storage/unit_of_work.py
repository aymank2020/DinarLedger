"""
dinarledger.storage.unit_of_work — Transaction wrapper for grouped operations.

Groups multiple repository mutations into a single logical transaction
with automatic rollback on failure.  Works with both
:class:`JsonRepository` and :class:`SqliteRepository`.
"""

from __future__ import annotations

from typing import Any

from .base import Repository


class UnitOfWork:
    """Context manager that groups repository operations into a transaction.

    For :class:`SqliteRepository`, this uses real database transactions.
    For :class:`JsonRepository` and :class:`MemoryRepository`, it
    simulates atomicity by snapshotting state on entry and restoring it
    on rollback.

    Parameters
    ----------
    repositories : Repository
        One or more repositories participating in the unit of work.

    Examples
    --------
    >>> from dinarledger.storage.unit_of_work import UnitOfWork
    >>> with UnitOfWork(customer_repo, invoice_repo) as uow:
    ...     customer_repo.add(customer)
    ...     invoice_repo.add(invoice)
    ...     # If invoice_repo.add fails, customer_repo is rolled back
    """

    def __init__(self, *repositories: Repository) -> None:
        self._repos = repositories
        self._snapshots: list[Any] = []
        self._committed = False
        self._rolled_back = False

    def __enter__(self) -> UnitOfWork:
        self._begin()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        if exc_type is not None:
            self._rollback()
            return False  # re-raise the exception
        if not self._committed and not self._rolled_back:
            self.commit()
        return False

    # -- Internal lifecycle ---------------------------------------------------

    def _begin(self) -> None:
        """Start the unit of work — snapshot state / begin transactions."""
        from .json_store import JsonRepository
        from .memory import MemoryRepository
        from .sqlite_store import SqliteRepository

        for repo in self._repos:
            if isinstance(repo, SqliteRepository):
                repo.begin()
            elif isinstance(repo, MemoryRepository):
                # Snapshot the store for possible rollback
                import copy
                self._snapshots.append(copy.deepcopy(repo._store))
            elif isinstance(repo, JsonRepository):
                # Snapshot the store (force load first)
                repo._ensure_loaded()
                import copy
                assert repo._store is not None
                self._snapshots.append(copy.deepcopy(repo._store))

    def commit(self) -> None:
        """Commit all changes across all repositories."""
        from .sqlite_store import SqliteRepository

        for repo in self._repos:
            if isinstance(repo, SqliteRepository):
                repo.commit()

        self._committed = True

    def _rollback(self) -> None:
        """Roll back all changes across all repositories."""
        from .json_store import JsonRepository
        from .memory import MemoryRepository
        from .sqlite_store import SqliteRepository

        snapshot_idx = 0
        for repo in self._repos:
            if isinstance(repo, SqliteRepository):
                repo.rollback()
            elif isinstance(repo, (MemoryRepository, JsonRepository)):
                if snapshot_idx < len(self._snapshots):
                    repo._store = self._snapshots[snapshot_idx]
                    snapshot_idx += 1
                    # For JsonRepository, also persist the rolled-back state
                    if isinstance(repo, JsonRepository) and repo._auto_save:
                        repo._save()

        self._rolled_back = True

    def rollback(self) -> None:
        """Public rollback — can be called explicitly inside the context."""
        self._rollback()
