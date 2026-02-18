from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Any

from psycopg import Connection

from app.core.database import get_connection
from app.models.entities import TicketEntity, TicketStatus


def _to_ticket_entity(row: dict[str, Any]) -> TicketEntity:
    return TicketEntity(
        id=row["id"],
        title=row["title"],
        description=row["description"],
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        completed_at=row["completed_at"],
    )


class TicketRepository:
    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url

    @contextmanager
    def _use_connection(self, connection: Connection | None) -> Iterator[Connection]:
        if connection is not None:
            yield connection
            return
        with get_connection(self.database_url) as managed:
            yield managed

    def create(
        self,
        *,
        title: str,
        description: str | None = None,
        status: TicketStatus = "open",
        completed_at: datetime | None = None,
        connection: Connection | None = None,
    ) -> TicketEntity:
        query = """
            INSERT INTO tickets (title, description, status, completed_at)
            VALUES (%s, %s, %s, %s)
            RETURNING id, title, description, status, created_at, updated_at, completed_at
        """
        with self._use_connection(connection) as active_connection:
            with active_connection.cursor() as cursor:
                cursor.execute(query, (title, description, status, completed_at))
                created = cursor.fetchone()
        if created is None:
            raise RuntimeError("Failed to create ticket.")
        return _to_ticket_entity(created)

    def get_by_id(
        self,
        ticket_id: int,
        connection: Connection | None = None,
    ) -> TicketEntity | None:
        query = """
            SELECT id, title, description, status, created_at, updated_at, completed_at
            FROM tickets
            WHERE id = %s
        """
        with self._use_connection(connection) as active_connection:
            with active_connection.cursor() as cursor:
                cursor.execute(query, (ticket_id,))
                row = cursor.fetchone()
        if row is None:
            return None
        return _to_ticket_entity(row)

    def update(
        self,
        *,
        ticket_id: int,
        title: str,
        description: str | None,
        status: TicketStatus,
        completed_at: datetime | None,
        connection: Connection | None = None,
    ) -> TicketEntity | None:
        query = """
            UPDATE tickets
            SET title = %s,
                description = %s,
                status = %s,
                completed_at = %s,
                updated_at = NOW()
            WHERE id = %s
            RETURNING id, title, description, status, created_at, updated_at, completed_at
        """
        with self._use_connection(connection) as active_connection:
            with active_connection.cursor() as cursor:
                cursor.execute(query, (title, description, status, completed_at, ticket_id))
                row = cursor.fetchone()
        if row is None:
            return None
        return _to_ticket_entity(row)

    def delete(self, ticket_id: int, connection: Connection | None = None) -> bool:
        query = "DELETE FROM tickets WHERE id = %s"
        with self._use_connection(connection) as active_connection:
            with active_connection.cursor() as cursor:
                cursor.execute(query, (ticket_id,))
                return cursor.rowcount > 0

    def list(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        connection: Connection | None = None,
    ) -> list[TicketEntity]:
        query = """
            SELECT id, title, description, status, created_at, updated_at, completed_at
            FROM tickets
            ORDER BY id DESC
            LIMIT %s OFFSET %s
        """
        with self._use_connection(connection) as active_connection:
            with active_connection.cursor() as cursor:
                cursor.execute(query, (limit, offset))
                rows = cursor.fetchall()
        return [_to_ticket_entity(row) for row in rows]

    def list_filtered(
        self,
        *,
        tag_id: int | None,
        q: str | None,
        status: TicketStatus | None,
        limit: int,
        offset: int,
        connection: Connection | None = None,
    ) -> tuple[list[TicketEntity], int]:
        where_clauses: list[str] = []
        params: list[Any] = []

        if status is not None:
            where_clauses.append("t.status = %s")
            params.append(status)

        if q:
            where_clauses.append("t.title ILIKE %s")
            params.append(f"%{q}%")

        if tag_id is not None:
            where_clauses.append(
                "EXISTS (SELECT 1 FROM ticket_tags tt WHERE tt.ticket_id = t.id AND tt.tag_id = %s)"
            )
            params.append(tag_id)

        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        list_query = f"""
            SELECT
                t.id,
                t.title,
                t.description,
                t.status,
                t.created_at,
                t.updated_at,
                t.completed_at
            FROM tickets t
            {where_sql}
            ORDER BY t.id DESC
            LIMIT %s OFFSET %s
        """
        count_query = f"""
            SELECT COUNT(1) AS total
            FROM tickets t
            {where_sql}
        """
        list_params = [*params, limit, offset]

        with self._use_connection(connection) as active_connection:
            with active_connection.cursor() as cursor:
                cursor.execute(count_query, params)
                count_row = cursor.fetchone()
                total = int(count_row["total"]) if count_row is not None else 0

                cursor.execute(list_query, list_params)
                rows = cursor.fetchall()

        return ([_to_ticket_entity(row) for row in rows], total)
