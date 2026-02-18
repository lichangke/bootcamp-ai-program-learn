from collections.abc import Iterator
from contextlib import contextmanager

from psycopg import Connection

from app.core.database import get_connection


class TicketTagRepository:
    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url

    @contextmanager
    def _use_connection(self, connection: Connection | None) -> Iterator[Connection]:
        if connection is not None:
            yield connection
            return
        with get_connection(self.database_url) as managed:
            yield managed

    def add_tag(self, *, ticket_id: int, tag_id: int, connection: Connection | None = None) -> None:
        query = """
            INSERT INTO ticket_tags (ticket_id, tag_id)
            VALUES (%s, %s)
            ON CONFLICT (ticket_id, tag_id) DO NOTHING
        """
        with self._use_connection(connection) as active_connection:
            with active_connection.cursor() as cursor:
                cursor.execute(query, (ticket_id, tag_id))

    def remove_tag(
        self,
        *,
        ticket_id: int,
        tag_id: int,
        connection: Connection | None = None,
    ) -> bool:
        query = "DELETE FROM ticket_tags WHERE ticket_id = %s AND tag_id = %s"
        with self._use_connection(connection) as active_connection:
            with active_connection.cursor() as cursor:
                cursor.execute(query, (ticket_id, tag_id))
                return cursor.rowcount > 0

    def replace_tags(
        self,
        *,
        ticket_id: int,
        tag_ids: list[int],
        connection: Connection | None = None,
    ) -> None:
        deduped_tag_ids = list(dict.fromkeys(tag_ids))

        with self._use_connection(connection) as active_connection:
            with active_connection.cursor() as cursor:
                cursor.execute("DELETE FROM ticket_tags WHERE ticket_id = %s", (ticket_id,))
                if deduped_tag_ids:
                    cursor.executemany(
                        "INSERT INTO ticket_tags (ticket_id, tag_id) VALUES (%s, %s)",
                        [(ticket_id, tag_id) for tag_id in deduped_tag_ids],
                    )

    def list_tag_ids(self, *, ticket_id: int, connection: Connection | None = None) -> list[int]:
        query = """
            SELECT tag_id
            FROM ticket_tags
            WHERE ticket_id = %s
            ORDER BY tag_id ASC
        """
        with self._use_connection(connection) as active_connection:
            with active_connection.cursor() as cursor:
                cursor.execute(query, (ticket_id,))
                rows = cursor.fetchall()
        return [row["tag_id"] for row in rows]

    def list_tag_ids_by_ticket_ids(
        self,
        *,
        ticket_ids: list[int],
        connection: Connection | None = None,
    ) -> dict[int, list[int]]:
        if not ticket_ids:
            return {}

        query = """
            SELECT ticket_id, tag_id
            FROM ticket_tags
            WHERE ticket_id = ANY(%s)
            ORDER BY ticket_id ASC, tag_id ASC
        """
        with self._use_connection(connection) as active_connection:
            with active_connection.cursor() as cursor:
                cursor.execute(query, (ticket_ids,))
                rows = cursor.fetchall()

        mapping: dict[int, list[int]] = {ticket_id: [] for ticket_id in ticket_ids}
        for row in rows:
            mapping[row["ticket_id"]].append(row["tag_id"])
        return mapping
