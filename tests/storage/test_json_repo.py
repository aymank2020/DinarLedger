"""Tests for the JSON file-backed repository.

Covers round-trip serialization, file persistence, atomic writes,
backup rotation, and lazy loading.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import pytest

from dinarledger.storage.json_store import JsonRepository
from dinarledger.storage.base import EntityNotFoundError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Item:
    """Minimal entity for JSON repo tests."""
    id: str
    name: str
    value: int


@pytest.fixture
def json_repo(tmp_path: Path) -> JsonRepository[Item]:
    file_path = tmp_path / "items.json"
    return JsonRepository(Item, file_path, backup_count=2, auto_save=True)


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

class TestJsonRepoCRUD:
    def test_add_and_get(self, json_repo: JsonRepository[Item]) -> None:
        entity = Item(id="i1", name="widget", value=42)
        json_repo.add(entity)
        result = json_repo.get("i1")
        assert result is not None
        assert result.name == "widget"
        assert result.value == 42

    def test_persists_to_disk(self, json_repo: JsonRepository[Item], tmp_path: Path) -> None:
        json_repo.add(Item(id="i1", name="widget", value=42))
        file_path = tmp_path / "items.json"
        assert file_path.exists()
        data = json.loads(file_path.read_text())
        assert "i1" in data

    def test_reload_from_disk(self, tmp_path: Path) -> None:
        file_path = tmp_path / "items.json"
        repo1 = JsonRepository(Item, file_path)
        repo1.add(Item(id="i1", name="widget", value=42))

        repo2 = JsonRepository(Item, file_path)
        result = repo2.get("i1")
        assert result is not None
        assert result.name == "widget"

    def test_get_all(self, json_repo: JsonRepository[Item]) -> None:
        json_repo.add(Item(id="i1", name="a", value=1))
        json_repo.add(Item(id="i2", name="b", value=2))
        all_items = json_repo.get_all()
        assert len(all_items) == 2

    def test_update(self, json_repo: JsonRepository[Item]) -> None:
        json_repo.add(Item(id="i1", name="old", value=1))
        json_repo.update(Item(id="i1", name="new", value=2))
        result = json_repo.get("i1")
        assert result.name == "new"
        assert result.value == 2

    def test_update_missing_raises(self, json_repo: JsonRepository[Item]) -> None:
        with pytest.raises(EntityNotFoundError):
            json_repo.update(Item(id="missing", name="x", value=0))

    def test_delete(self, json_repo: JsonRepository[Item]) -> None:
        json_repo.add(Item(id="i1", name="a", value=1))
        assert json_repo.delete("i1") is True
        assert json_repo.get("i1") is None
        assert json_repo.delete("i1") is False

    def test_find_by_field(self, json_repo: JsonRepository[Item]) -> None:
        json_repo.add(Item(id="i1", name="alpha", value=10))
        json_repo.add(Item(id="i2", name="beta", value=20))
        result = json_repo.find({"name": "alpha"})
        assert len(result) == 1
        assert result[0].id == "i1"


# ---------------------------------------------------------------------------
# Backups
# ---------------------------------------------------------------------------

class TestJsonRepoBackups:
    def test_backup_rotation(self, tmp_path: Path) -> None:
        file_path = tmp_path / "items.json"
        repo = JsonRepository(Item, file_path, backup_count=2, auto_save=True)

        repo.add(Item(id="i1", name="v1", value=1))
        repo.add(Item(id="i2", name="v2", value=2))
        repo.add(Item(id="i3", name="v3", value=3))

        assert (tmp_path / "items.bak.1").exists()
        # bak.1 should contain the state before the last write
        bak1 = json.loads((tmp_path / "items.bak.1").read_text())
        assert "i2" in bak1

    def test_no_backups_when_count_zero(self, tmp_path: Path) -> None:
        file_path = tmp_path / "items.json"
        repo = JsonRepository(Item, file_path, backup_count=0, auto_save=True)
        repo.add(Item(id="i1", name="a", value=1))
        repo.add(Item(id="i2", name="b", value=2))
        assert not (tmp_path / "items.bak.1").exists()


# ---------------------------------------------------------------------------
# Auto-save toggle
# ---------------------------------------------------------------------------

class TestJsonRepoAutoSave:
    def test_manual_flush(self, tmp_path: Path) -> None:
        file_path = tmp_path / "items.json"
        repo = JsonRepository(Item, file_path, auto_save=False)
        repo.add(Item(id="i1", name="a", value=1))
        # Not yet on disk (auto_save=False, but the add still triggers _ensure_loaded)
        repo.flush()
        assert file_path.exists()
