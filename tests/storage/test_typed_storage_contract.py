from dataclasses import dataclass
from typing import ClassVar

from dinarledger.storage.memory import MemoryRepository
from dinarledger.storage.serializers import EntitySerializer, register_entity
from dinarledger.storage.sqlite_store import SqliteRepository
from dinarledger.storage.unit_of_work import UnitOfWork


@dataclass(frozen=True)
class StorageContractEntity:
    id: str
    name: str
    category: ClassVar[str] = "metadata"


def test_sqlite_roundtrip_uses_dataclass_fields_and_public_keywords(tmp_path):
    repo = SqliteRepository(StorageContractEntity, tmp_path / "typed.db")
    first = StorageContractEntity("one", "first")
    second = StorageContractEntity("one", "updated")
    try:
        repo.add(first)
        assert repo.get(id="one") == first
        assert repo.find(filter={"name": "first"}) == [first]
        repo.update(second)
        assert repo.get(id="one") == second
        assert repo.count() == 1
        assert repo.delete(id="one")
        assert repo.count() == 0
    finally:
        repo.close()


def test_typed_repository_unit_of_work_and_dynamic_serializer():
    register_entity(StorageContractEntity)
    entity = StorageContractEntity("one", "first")
    assert EntitySerializer.deserialize(EntitySerializer.serialize(entity)) == entity
    repo = MemoryRepository(StorageContractEntity)
    try:
        with UnitOfWork(repo):
            repo.add(entity)
            raise ValueError("rollback")
    except ValueError:
        pass
    assert repo.get(id="one") is None
