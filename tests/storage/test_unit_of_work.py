"""Tests for the UnitOfWork transaction wrapper.

Covers commit and rollback across memory, JSON, and SQLite repositories.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from dinarledger.storage.json_store import JsonRepository
from dinarledger.storage.memory import MemoryRepository
from dinarledger.storage.sqlite_store import SqliteRepository
from dinarledger.storage.unit_of_work import UnitOfWork
from dinarledger.core.types import Customer
from dinarledger.core.money import Money
from decimal import Decimal


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Item:
    id: str
    name: str


@pytest.fixture
def mem_repo() -> MemoryRepository[Item]:
    return MemoryRepository(Item)


@pytest.fixture
def json_repo(tmp_path: Path) -> JsonRepository[Item]:
    return JsonRepository(Item, tmp_path / "items.json", backup_count=0)


@pytest.fixture
def sqlite_repo(tmp_path: Path) -> SqliteRepository[Item]:
    return SqliteRepository(Item, tmp_path / "test.db")


# ---------------------------------------------------------------------------
# Memory repository UoW
# ---------------------------------------------------------------------------

class TestUnitOfWorkMemory:
    def test_commit(self, mem_repo: MemoryRepository[Item]) -> None:
        with UnitOfWork(mem_repo) as uow:
            mem_repo.add(Item(id="i1", name="alpha"))
        assert mem_repo.get("i1") is not None

    def test_rollback_on_exception(self, mem_repo: MemoryRepository[Item]) -> None:
        try:
            with UnitOfWork(mem_repo):
                mem_repo.add(Item(id="i1", name="alpha"))
                raise RuntimeError("boom")
        except RuntimeError:
            pass
        assert mem_repo.get("i1") is None

    def test_explicit_rollback(self, mem_repo: MemoryRepository[Item]) -> None:
        with UnitOfWork(mem_repo) as uow:
            mem_repo.add(Item(id="i1", name="alpha"))
            uow.rollback()
        assert mem_repo.get("i1") is None


# ---------------------------------------------------------------------------
# JSON repository UoW
# ---------------------------------------------------------------------------

class TestUnitOfWorkJson:
    def test_commit(self, json_repo: JsonRepository[Item]) -> None:
        with UnitOfWork(json_repo):
            json_repo.add(Item(id="i1", name="alpha"))
        assert json_repo.get("i1") is not None

    def test_rollback_on_exception(self, json_repo: JsonRepository[Item]) -> None:
        try:
            with UnitOfWork(json_repo):
                json_repo.add(Item(id="i1", name="alpha"))
                raise RuntimeError("boom")
        except RuntimeError:
            pass
        assert json_repo.get("i1") is None


# ---------------------------------------------------------------------------
# SQLite repository UoW
# ---------------------------------------------------------------------------

class TestUnitOfWorkSqlite:
    def test_commit(self, sqlite_repo: SqliteRepository[Item]) -> None:
        with UnitOfWork(sqlite_repo):
            sqlite_repo.add(Item(id="i1", name="alpha"))
        assert sqlite_repo.get("i1") is not None

    def test_rollback_on_exception(self, sqlite_repo: SqliteRepository[Item]) -> None:
        try:
            with UnitOfWork(sqlite_repo):
                sqlite_repo.add(Item(id="i1", name="alpha"))
                raise RuntimeError("boom")
        except RuntimeError:
            pass
        assert sqlite_repo.get("i1") is None


# ---------------------------------------------------------------------------
# Multi-repo UoW
# ---------------------------------------------------------------------------

class TestUnitOfWorkMultiRepo:
    def test_rollback_across_repos(
        self,
        mem_repo: MemoryRepository[Item],
        tmp_path: Path,
    ) -> None:
        sqlite_repo = SqliteRepository(Item, tmp_path / "test.db")
        try:
            with UnitOfWork(mem_repo, sqlite_repo):
                mem_repo.add(Item(id="i1", name="alpha"))
                sqlite_repo.add(Item(id="i1", name="alpha"))
                raise RuntimeError("boom")
        except RuntimeError:
            pass
        assert mem_repo.get("i1") is None
        assert sqlite_repo.get("i1") is None
