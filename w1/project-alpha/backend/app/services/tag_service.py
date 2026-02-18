from fastapi import status
from psycopg.errors import UniqueViolation

from app.core.database import get_connection
from app.core.errors import AppError
from app.models.entities import TagEntity
from app.models.schemas.tag import TagRead, TagWriteRequest
from app.repositories.tag_repository import TagRepository


class TagService:
    def __init__(
        self,
        tag_repository: TagRepository,
        database_url: str | None = None,
    ) -> None:
        self.tag_repository = tag_repository
        self.database_url = database_url

    def list_tags(self) -> list[TagRead]:
        tags = self.tag_repository.list()
        return [self._to_tag_read(tag) for tag in tags]

    def create_tag(self, payload: TagWriteRequest) -> TagRead:
        name = self._validate_name(payload.name)

        try:
            created = self.tag_repository.create(name=name)
            return self._to_tag_read(created)
        except UniqueViolation as exc:
            self._raise_name_conflict(name=name, exc=exc)

    def update_tag(self, tag_id: int, payload: TagWriteRequest) -> TagRead:
        name = self._validate_name(payload.name)

        with get_connection(self.database_url) as connection:
            existing = self.tag_repository.get_by_id(tag_id, connection=connection)
            if existing is None:
                self._raise_tag_not_found(tag_id)

            try:
                updated = self.tag_repository.update(
                    tag_id=tag_id,
                    name=name,
                    connection=connection,
                )
            except UniqueViolation as exc:
                self._raise_name_conflict(name=name, exc=exc)

            if updated is None:
                self._raise_tag_not_found(tag_id)
            return self._to_tag_read(updated)

    def delete_tag(self, tag_id: int) -> None:
        with get_connection(self.database_url) as connection:
            existing = self.tag_repository.get_by_id(tag_id, connection=connection)
            if existing is None:
                self._raise_tag_not_found(tag_id)

            deleted = self.tag_repository.delete(tag_id, connection=connection)
            if not deleted:
                self._raise_tag_not_found(tag_id)

    def _to_tag_read(self, tag: TagEntity) -> TagRead:
        return TagRead(
            id=tag.id,
            name=tag.name,
            created_at=tag.created_at,
            updated_at=tag.updated_at,
        )

    def _validate_name(self, name: str) -> str:
        normalized = name.strip()
        if not 1 <= len(normalized) <= 50:
            raise AppError(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="INVALID_TAG_NAME",
                message="Tag name length must be between 1 and 50 characters.",
            )
        return normalized

    def _raise_name_conflict(self, *, name: str, exc: UniqueViolation) -> None:
        raise AppError(
            status_code=status.HTTP_409_CONFLICT,
            code="TAG_NAME_CONFLICT",
            message="Tag name already exists.",
            details={"name": name},
        ) from exc

    def _raise_tag_not_found(self, tag_id: int) -> None:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="TAG_NOT_FOUND",
            message="Tag not found.",
            details={"tag_id": tag_id},
        )
