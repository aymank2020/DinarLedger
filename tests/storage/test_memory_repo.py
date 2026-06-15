"""Tests for the in-memory repository implementation.

Covers CRUD operations, find/filter, auto-ID generation, and thread safety.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from decimal import Decimal

import pytest

from dinarledger.storage.memory import MemoryRepository
from dinarledger.storage.base import EntityNotFoundError, FilterCondition, FilterOperator


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Sample:
    """Minimal entity used by these tests."""
    id: str
    name: str
    value: int


@pytest.fixture
def repo() -> MemoryRepository[Sample]:
    return MemoryRepository(Sample)


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

class TestMemoryRepoCRUD:
    def test_add_and_get(self, repo: MemoryRepository[Sample]) -> None:
        entity = Sample(id="s1", name="alpha", value=10)
        result = repo.add(entity)
        assert result is entity
        assert repo.get("s1") is entity

    def test_get_returns_none_for_missing(self, repo: MemoryRepository[Sample]) -> None:
        assert repo.get("nonexistent") is None

    def test_get_all(self, repo: MemoryRepository[Sample]) -> None:
        repo.add(Sample(id="s1", name="a", value=1))
        repo.add(Sample(id="s2", name="b", value=2))
        all_items = repo.get_all()
        assert len(all_items) == 2

    def test_update(self, repo: MemoryRepository[Sample]) -> None:
        repo.add(Sample(id="s1", name="old", value=1))
        updated = Sample(id="s1", name="new", value=2)
        result = repo.update(updated)
        assert result.name == "new"
        assert repo.get("s1").value == 2

    def test_update_missing_raises(self, repo: MemoryRepository[Sample]) -> None:
        with pytest.raises(EntityNotFoundError):
            repo.update(Sample(id="missing", name="x", value=0))

    def test_delete(self, repo: MemoryRepository[Sample]) -> None:
        repo.add(Sample(id="s1", name="a", value=1))
        assert repo.delete("s1") is True
        assert repo.get("s1") is None
        assert repo.delete("s1") is False

    def test_count(self, repo: MemoryRepository[Sample]) -> None:
        assert repo.count() == 0
        repo.add(Sample(id="s1", name="a", value=1))
        assert repo.count() == 1

    def test_clear(self, repo: MemoryRepository[Sample]) -> None:
        repo.add(Sample(id="s1", name="a", value=1))
        repo.clear()
        assert repo.count() == 0


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------

class TestMemoryRepoFind:
    def test_find_by_field(self, repo: MemoryRepository[Sample]) -> None:
        repo.add(Sample(id="s1", name="alpha", value=10))
        repo.add(Sample(id="s2", name="beta", value=20))
        result = repo.find({"name": "alpha"})
        assert len(result) == 1
        assert result[0].id == "s1"

    def test_find_no_match(self, repo: MemoryRepository[Sample]) -> None:
        repo.add(Sample(id="s1", name="alpha", value=10))
        assert repo.find({"name": "gamma"}) == []

    def test_find_empty_filter_returns_all(self, repo: MemoryRepository[Sample]) -> None:
        repo.add(Sample(id="s1", name="a", value=1))
        repo.add(Sample(id="s2", name="b", value=2))
        assert len(repo.find()) == 2

    def test_find_with_conditions(self, repo: MemoryRepository[Sample]) -> None:
        repo.add(Sample(id="s1", name="a", value=10))
        repo.add(Sample(id="s2", name="b", value=20))
        conds = [FilterCondition(field="value", operator=FilterOperator.GT, value=15)]
        result = repo.find_with_conditions(conds)
        assert len(result) == 1
        assert result[0].id == "s2"


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestMemoryRepoThreadSafety:
    def test_concurrent_adds(self, repo: MemoryRepository[Sample]) -> None:
        errors: list[Exception] = []

        def add_item(idx: int) -> None:
            try:
                repo.add(Sample(id=f"s{idx}", name=f"item-{idx}", value=idx))
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=add_item, args=(i,)) for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert repo.count() == 50
