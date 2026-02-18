from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from psycopg import Connection

from app.core.database import get_connection
from app.models.entities import TagEntity


def _to_tag_entity(row: dict[str, Any]) -> TagEntity:
    return TagEntity(
        id=row["id"],
        name=row["name"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class TagRepository:
    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url

    @contextmanager
    def _use_connection(self, connection: Connection | None) -> Iterator[Connection]:
        if connection is not None:
            yield connection
            return
        with get_connection(self.database_url) as managed:
            yield managed

    def create(self, *, name: str, connection: Connection | None = None) -> TagEntity:
        query = """
            INSERT INTO tags (name)
            VALUES (%s)
            RETURNING id, name, created_at, updated_at
        """
        with self._use_connection(connection) as active_connection:
            with active_connection.cursor() as cursor:
                cursor.execute(query, (name,))
                row = cursor.fetchone()
        if row is None:
            raise RuntimeError("Failed to create tag.")
        return _to_tag_entity(row)

    def get_by_id(self, tag_id: int, connection: Connection | None = None) -> TagEntity | None:
        query = """
            SELECT id, name, created_at, updated_at
            FROM tags
            WHERE id = %s
        """
        with self._use_connection(connection) as active_connection:
            with active_connection.cursor() as cursor:
                cursor.execute(query, (tag_id,))
                row = cursor.fetchone()
        if row is None:
            return None
        return _to_tag_entity(row)

    def update(
        self,
        *,
        tag_id: int,
        name: str,
        connection: Connection | None = None,
    ) -> TagEntity | None:
        query = """
            UPDATE tags
            SET name = %s,
                updated_at = NOW()
            WHERE id = %s
            RETURNING id, name, created_at, updated_at
        """
        with self._use_connection(connection) as active_connection:
            with active_connection.cursor() as cursor:
                cursor.execute(query, (name, tag_id))
                row = cursor.fetchone()
        if row is None:
            return None
        return _to_tag_entity(row)

    def delete(self, tag_id: int, connection: Connection | None = None) -> bool:
        query = "DELETE FROM tags WHERE id = %s"
        with self._use_connection(connection) as active_connection:
            with active_connection.cursor() as cursor:
                cursor.execute(query, (tag_id,))
                return cursor.rowcount > 0

    def list(self, connection: Connection | None = None) -> list[TagEntity]:
        query = """
            SELECT id, name, created_at, updated_at
            FROM tags
            ORDER BY id ASC
        """
        with self._use_connection(connection) as active_connection:
            with active_connection.cursor() as cursor:
                cursor.execute(query)
                rows = cursor.fetchall()
        return [_to_tag_entity(row) for row in rows]

    def list_by_ids(
        self,
        tag_ids: list[int],
        connection: Connection | None = None,
    ) -> list[TagEntity]:
        if not tag_ids:
            return []

        query = """
            SELECT id, name, created_at, updated_at
            FROM tags
            WHERE id = ANY(%s)
            ORDER BY id ASC
        """
        with self._use_connection(connection) as active_connection:
            with active_connection.cursor() as cursor:
                cursor.execute(query, (tag_ids,))
                rows = cursor.fetchall()
        return [_to_tag_entity(row) for row in rows]
