from datetime import UTC, datetime

from app.api.routes.tags import get_tag_service
from app.core.errors import AppError
from app.main import app
from app.models.schemas.tag import TagRead, TagWriteRequest
from fastapi import status
from fastapi.testclient import TestClient


class _FakeTagService:
    def __init__(self) -> None:
        now = datetime.now(UTC)
        self.tags = {
            1: TagRead(id=1, name="backend", created_at=now, updated_at=now),
            2: TagRead(id=2, name="urgent", created_at=now, updated_at=now),
        }

    def list_tags(self) -> list[TagRead]:
        return list(self.tags.values())

    def create_tag(self, payload: TagWriteRequest) -> TagRead:
        now = datetime.now(UTC)
        created = TagRead(
            id=3,
            name=payload.name.strip(),
            created_at=now,
            updated_at=now,
        )
        self.tags[created.id] = created
        return created

    def update_tag(self, tag_id: int, payload: TagWriteRequest) -> TagRead:
        existing = self.tags.get(tag_id)
        if existing is None:
            raise AppError(
                status_code=status.HTTP_404_NOT_FOUND,
                code="TAG_NOT_FOUND",
                message="Tag not found.",
            )
        updated = existing.model_copy(
            update={
                "name": payload.name.strip(),
                "updated_at": datetime.now(UTC),
            }
        )
        self.tags[tag_id] = updated
        return updated

    def delete_tag(self, tag_id: int) -> None:
        if tag_id not in self.tags:
            raise AppError(
                status_code=status.HTTP_404_NOT_FOUND,
                code="TAG_NOT_FOUND",
                message="Tag not found.",
            )
        self.tags.pop(tag_id)


def test_tag_api_routes(client: TestClient) -> None:
    service = _FakeTagService()
    app.dependency_overrides[get_tag_service] = lambda: service

    list_response = client.get("/api/tags")
    assert list_response.status_code == status.HTTP_200_OK
    assert len(list_response.json()["data"]) == 2

    create_response = client.post("/api/tags", json={"name": "frontend"})
    assert create_response.status_code == status.HTTP_201_CREATED
    assert create_response.json()["data"]["name"] == "frontend"

    update_response = client.put("/api/tags/1", json={"name": "platform"})
    assert update_response.status_code == status.HTTP_200_OK
    assert update_response.json()["data"]["name"] == "platform"

    delete_response = client.delete("/api/tags/2")
    assert delete_response.status_code == status.HTTP_204_NO_CONTENT

    app.dependency_overrides.clear()


def test_tag_api_error_structure(client: TestClient) -> None:
    service = _FakeTagService()
    app.dependency_overrides[get_tag_service] = lambda: service

    response = client.put("/api/tags/404", json={"name": "oops"})
    assert response.status_code == status.HTTP_404_NOT_FOUND
    payload = response.json()
    assert payload["error"]["code"] == "TAG_NOT_FOUND"
    assert isinstance(payload["error"]["details"], dict)

    app.dependency_overrides.clear()
