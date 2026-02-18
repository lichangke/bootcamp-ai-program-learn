from datetime import UTC, datetime

from fastapi import status
from psycopg import Connection
from psycopg.errors import ForeignKeyViolation

from app.core.database import get_connection
from app.core.errors import AppError
from app.models.entities import TicketStatus
from app.models.schemas.ticket import (
    TicketListMeta,
    TicketListResponse,
    TicketRead,
    TicketWriteRequest,
)
from app.repositories.tag_repository import TagRepository
from app.repositories.ticket_repository import TicketRepository
from app.repositories.ticket_tag_repository import TicketTagRepository


class TicketService:
    def __init__(
        self,
        ticket_repository: TicketRepository,
        ticket_tag_repository: TicketTagRepository,
        tag_repository: TagRepository,
        database_url: str | None = None,
    ) -> None:
        self.ticket_repository = ticket_repository
        self.ticket_tag_repository = ticket_tag_repository
        self.tag_repository = tag_repository
        self.database_url = database_url

    def create_ticket(self, payload: TicketWriteRequest) -> TicketRead:
        title = self._validate_title(payload.title)

        try:
            with get_connection(self.database_url) as connection:
                tag_ids = self._validate_tag_ids(payload.tag_ids, connection=connection)
                ticket = self.ticket_repository.create(
                    title=title,
                    description=payload.description,
                    connection=connection,
                )
                self.ticket_tag_repository.replace_tags(
                    ticket_id=ticket.id,
                    tag_ids=tag_ids,
                    connection=connection,
                )
                return self._build_ticket_read(ticket_id=ticket.id, connection=connection)
        except ForeignKeyViolation as exc:
            raise AppError(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="INVALID_TAG_IDS",
                message="Some tag IDs do not exist.",
                details={"tag_ids": tag_ids},
            ) from exc

    def list_tickets(
        self,
        *,
        tag_id: int | None,
        q: str | None,
        status: TicketStatus | None,
        page: int,
        page_size: int,
    ) -> TicketListResponse:
        normalized_q = q.strip() if q else None
        offset = (page - 1) * page_size

        with get_connection(self.database_url) as connection:
            tickets, total = self.ticket_repository.list_filtered(
                tag_id=tag_id,
                q=normalized_q,
                status=status,
                limit=page_size,
                offset=offset,
                connection=connection,
            )
            tag_mapping = self.ticket_tag_repository.list_tag_ids_by_ticket_ids(
                ticket_ids=[ticket.id for ticket in tickets],
                connection=connection,
            )

        items = [
            TicketRead(
                id=ticket.id,
                title=ticket.title,
                description=ticket.description,
                status=ticket.status,
                tag_ids=tag_mapping.get(ticket.id, []),
                created_at=ticket.created_at,
                updated_at=ticket.updated_at,
                completed_at=ticket.completed_at,
            )
            for ticket in tickets
        ]
        return TicketListResponse(
            data=items,
            meta=TicketListMeta(
                page=page,
                page_size=page_size,
                total=total,
            ),
        )

    def get_ticket(self, ticket_id: int) -> TicketRead:
        with get_connection(self.database_url) as connection:
            ticket = self.ticket_repository.get_by_id(ticket_id, connection=connection)
            if ticket is None:
                self._raise_ticket_not_found(ticket_id)
            return self._build_ticket_read(ticket_id=ticket_id, connection=connection)

    def update_ticket(self, ticket_id: int, payload: TicketWriteRequest) -> TicketRead:
        title = self._validate_title(payload.title)

        with get_connection(self.database_url) as connection:
            tag_ids = self._validate_tag_ids(payload.tag_ids, connection=connection)
            current_ticket = self.ticket_repository.get_by_id(ticket_id, connection=connection)
            if current_ticket is None:
                self._raise_ticket_not_found(ticket_id)

            updated = self.ticket_repository.update(
                ticket_id=ticket_id,
                title=title,
                description=payload.description,
                status=current_ticket.status,
                completed_at=current_ticket.completed_at,
                connection=connection,
            )
            if updated is None:
                self._raise_ticket_not_found(ticket_id)

            try:
                self.ticket_tag_repository.replace_tags(
                    ticket_id=ticket_id,
                    tag_ids=tag_ids,
                    connection=connection,
                )
            except ForeignKeyViolation as exc:
                raise AppError(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="INVALID_TAG_IDS",
                    message="Some tag IDs do not exist.",
                    details={"tag_ids": tag_ids},
                ) from exc

            return self._build_ticket_read(ticket_id=ticket_id, connection=connection)

    def delete_ticket(self, ticket_id: int) -> None:
        deleted = self.ticket_repository.delete(ticket_id=ticket_id)
        if not deleted:
            self._raise_ticket_not_found(ticket_id)

    def complete_ticket(self, ticket_id: int) -> TicketRead:
        with get_connection(self.database_url) as connection:
            current_ticket = self.ticket_repository.get_by_id(ticket_id, connection=connection)
            if current_ticket is None:
                self._raise_ticket_not_found(ticket_id)

            if current_ticket.status != "done":
                self.ticket_repository.update(
                    ticket_id=ticket_id,
                    title=current_ticket.title,
                    description=current_ticket.description,
                    status="done",
                    completed_at=datetime.now(UTC),
                    connection=connection,
                )

            return self._build_ticket_read(ticket_id=ticket_id, connection=connection)

    def reopen_ticket(self, ticket_id: int) -> TicketRead:
        with get_connection(self.database_url) as connection:
            current_ticket = self.ticket_repository.get_by_id(ticket_id, connection=connection)
            if current_ticket is None:
                self._raise_ticket_not_found(ticket_id)

            if current_ticket.status != "open":
                self.ticket_repository.update(
                    ticket_id=ticket_id,
                    title=current_ticket.title,
                    description=current_ticket.description,
                    status="open",
                    completed_at=None,
                    connection=connection,
                )

            return self._build_ticket_read(ticket_id=ticket_id, connection=connection)

    def _build_ticket_read(
        self,
        ticket_id: int,
        connection: Connection | None = None,
    ) -> TicketRead:
        ticket = self.ticket_repository.get_by_id(ticket_id=ticket_id, connection=connection)
        if ticket is None:
            self._raise_ticket_not_found(ticket_id)

        tag_ids = self.ticket_tag_repository.list_tag_ids(
            ticket_id=ticket_id,
            connection=connection,
        )
        return TicketRead(
            id=ticket.id,
            title=ticket.title,
            description=ticket.description,
            status=ticket.status,
            tag_ids=tag_ids,
            created_at=ticket.created_at,
            updated_at=ticket.updated_at,
            completed_at=ticket.completed_at,
        )

    def _validate_title(self, title: str) -> str:
        normalized = title.strip()
        if not 1 <= len(normalized) <= 200:
            raise AppError(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="INVALID_TICKET_TITLE",
                message="Ticket title length must be between 1 and 200 characters.",
            )
        return normalized

    def _validate_tag_ids(
        self,
        tag_ids: list[int],
        connection: Connection | None = None,
    ) -> list[int]:
        deduped_tag_ids = list(dict.fromkeys(tag_ids))
        if not deduped_tag_ids:
            return deduped_tag_ids

        existing = self.tag_repository.list_by_ids(deduped_tag_ids, connection=connection)
        existing_ids = {tag.id for tag in existing}
        missing_ids = [tag_id for tag_id in deduped_tag_ids if tag_id not in existing_ids]
        if missing_ids:
            raise AppError(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="INVALID_TAG_IDS",
                message="Some tag IDs do not exist.",
                details={"missing_tag_ids": missing_ids},
            )
        return deduped_tag_ids

    def _raise_ticket_not_found(self, ticket_id: int) -> None:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="TICKET_NOT_FOUND",
            message="Ticket not found.",
            details={"ticket_id": ticket_id},
        )
