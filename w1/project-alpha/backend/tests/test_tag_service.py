from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

import pytest
from app.core.errors import AppError
from app.models.entities import TagEntity
from app.models.schemas.tag import TagWriteRequest
from app.services.tag_service import TagService
from fastapi import status
from psycopg.errors import UniqueViolation


@contextmanager
def _fake_connection(_: str | None = None) -> Iterator[object]:
    yield object()


class _FakeTagRepository:
    def __init__(self) -> None:
        now = datetime.now(UTC)
        self.tags: dict[int, TagEntity] = {
            1: TagEntity(id=1, name="backend", created_at=now, updated_at=now),
            2: TagEntity(id=2, name="urgent", created_at=now, updated_at=now),
        }
        self.raise_conflict = False

    def list(self, connection: object | None = None) -> list[TagEntity]:
        return list(self.tags.values())

    def create(self, *, name: str, connection: object | None = None) -> TagEntity:
        if self.raise_conflict:
            raise UniqueViolation("duplicate")
        now = datetime.now(UTC)
        created = TagEntity(id=3, name=name, created_at=now, updated_at=now)
        self.tags[created.id] = created
        return created

    def get_by_id(self, tag_id: int, connection: object | None = None) -> TagEntity | None:
        return self.tags.get(tag_id)

    def update(
        self,
        *,
        tag_id: int,
        name: str,
        connection: object | None = None,
    ) -> TagEntity | None:
        if self.raise_conflict:
            raise UniqueViolation("duplicate")
        current = self.tags.get(tag_id)
        if current is None:
            return None
        updated = TagEntity(
            id=current.id,
            name=name,
            created_at=current.created_at,
            updated_at=datetime.now(UTC),
        )
        self.tags[tag_id] = updated
        return updated

    def delete(self, tag_id: int, connection: object | None = None) -> bool:
        return self.tags.pop(tag_id, None) is not None


@pytest.fixture
def tag_service(monkeypatch: pytest.MonkeyPatch) -> TagService:
    monkeypatch.setattr("app.services.tag_service.get_connection", _fake_connection)
    return TagService(tag_repository=_FakeTagRepository())


def test_tag_service_validates_name(tag_service: TagService) -> None:
    with pytest.raises(AppError) as exc:
        tag_service.create_tag(TagWriteRequest(name="   "))
    assert exc.value.status_code == status.HTTP_400_BAD_REQUEST
    assert exc.value.code == "INVALID_TAG_NAME"


def test_tag_service_handles_name_conflict(tag_service: TagService) -> None:
    tag_service.tag_repository.raise_conflict = True
    with pytest.raises(AppError) as exc:
        tag_service.create_tag(TagWriteRequest(name="backend"))
    assert exc.value.status_code == status.HTTP_409_CONFLICT
    assert exc.value.code == "TAG_NAME_CONFLICT"


def test_tag_service_update_and_delete(tag_service: TagService) -> None:
    updated = tag_service.update_tag(1, TagWriteRequest(name="platform"))
    assert updated.name == "platform"

    tag_service.delete_tag(1)
    with pytest.raises(AppError) as exc:
        tag_service.delete_tag(1)
    assert exc.value.status_code == status.HTTP_404_NOT_FOUND
    assert exc.value.code == "TAG_NOT_FOUND"


def test_tag_service_list(tag_service: TagService) -> None:
    tags = tag_service.list_tags()
    assert len(tags) == 2
