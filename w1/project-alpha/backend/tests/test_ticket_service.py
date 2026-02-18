from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

import pytest
from app.core.errors import AppError
from app.models.entities import TagEntity, TicketEntity
from app.models.schemas.ticket import TicketWriteRequest
from app.services.ticket_service import TicketService
from fastapi import status


@contextmanager
def _fake_connection(_: str | None = None) -> Iterator[object]:
    yield object()


class _FakeTicketRepository:
    def __init__(self) -> None:
        now = datetime.now(UTC)
        self.store: dict[int, TicketEntity] = {
            1: TicketEntity(
                id=1,
                title="Initial ticket",
                description="seed data",
                status="open",
                created_at=now,
                updated_at=now,
                completed_at=None,
            )
        }
        self._next_id = 2

    def create(
        self,
        *,
        title: str,
        description: str | None = None,
        status: str = "open",
        completed_at: datetime | None = None,
        connection: object | None = None,
    ) -> TicketEntity:
        now = datetime.now(UTC)
        ticket = TicketEntity(
            id=self._next_id,
            title=title,
            description=description,
            status=status,
            created_at=now,
            updated_at=now,
            completed_at=completed_at,
        )
        self.store[ticket.id] = ticket
        self._next_id += 1
        return ticket

    def get_by_id(self, ticket_id: int, connection: object | None = None) -> TicketEntity | None:
        return self.store.get(ticket_id)

    def update(
        self,
        *,
        ticket_id: int,
        title: str,
        description: str | None,
        status: str,
        completed_at: datetime | None,
        connection: object | None = None,
    ) -> TicketEntity | None:
        current = self.store.get(ticket_id)
        if current is None:
            return None

        updated = TicketEntity(
            id=current.id,
            title=title,
            description=description,
            status=status,
            created_at=current.created_at,
            updated_at=datetime.now(UTC),
            completed_at=completed_at,
        )
        self.store[ticket_id] = updated
        return updated

    def delete(self, ticket_id: int, connection: object | None = None) -> bool:
        return self.store.pop(ticket_id, None) is not None

    def list_filtered(
        self,
        *,
        tag_id: int | None,
        q: str | None,
        status: str | None,
        limit: int,
        offset: int,
        connection: object | None = None,
    ) -> tuple[list[TicketEntity], int]:
        items = list(self.store.values())
        if status is not None:
            items = [item for item in items if item.status == status]
        if q:
            items = [item for item in items if q.lower() in item.title.lower()]
        if tag_id is not None and tag_id != 1:
            items = []

        total = len(items)
        sliced = items[offset : offset + limit]
        return (sliced, total)


class _FakeTagRepository:
    def __init__(self, existing_ids: list[int]) -> None:
        now = datetime.now(UTC)
        self.store = {
            tag_id: TagEntity(id=tag_id, name=f"tag-{tag_id}", created_at=now, updated_at=now)
            for tag_id in existing_ids
        }

    def list_by_ids(self, tag_ids: list[int], connection: object | None = None) -> list[TagEntity]:
        return [self.store[tag_id] for tag_id in tag_ids if tag_id in self.store]


class _FakeTicketTagRepository:
    def __init__(self) -> None:
        self.links: dict[int, list[int]] = {1: [1, 2]}

    def replace_tags(
        self,
        *,
        ticket_id: int,
        tag_ids: list[int],
        connection: object | None = None,
    ) -> None:
        self.links[ticket_id] = list(dict.fromkeys(tag_ids))

    def list_tag_ids(self, *, ticket_id: int, connection: object | None = None) -> list[int]:
        return self.links.get(ticket_id, [])

    def list_tag_ids_by_ticket_ids(
        self,
        *,
        ticket_ids: list[int],
        connection: object | None = None,
    ) -> dict[int, list[int]]:
        return {ticket_id: self.links.get(ticket_id, []) for ticket_id in ticket_ids}


@pytest.fixture
def ticket_service(monkeypatch: pytest.MonkeyPatch) -> TicketService:
    monkeypatch.setattr("app.services.ticket_service.get_connection", _fake_connection)
    return TicketService(
        ticket_repository=_FakeTicketRepository(),
        ticket_tag_repository=_FakeTicketTagRepository(),
        tag_repository=_FakeTagRepository(existing_ids=[1, 2, 3]),
    )


def test_create_ticket_rejects_blank_title(ticket_service: TicketService) -> None:
    with pytest.raises(AppError) as exc:
        ticket_service.create_ticket(
            TicketWriteRequest(
                title="   ",
                description="invalid ticket",
                tag_ids=[],
            )
        )
    assert exc.value.status_code == status.HTTP_400_BAD_REQUEST
    assert exc.value.code == "INVALID_TICKET_TITLE"


def test_create_ticket_rejects_missing_tag_id(ticket_service: TicketService) -> None:
    with pytest.raises(AppError) as exc:
        ticket_service.create_ticket(
            TicketWriteRequest(
                title="Need valid tags",
                description=None,
                tag_ids=[999],
            )
        )
    assert exc.value.status_code == status.HTTP_400_BAD_REQUEST
    assert exc.value.code == "INVALID_TAG_IDS"
    assert exc.value.details["missing_tag_ids"] == [999]


def test_update_ticket_replaces_tags_full_set(ticket_service: TicketService) -> None:
    ticket = ticket_service.update_ticket(
        1,
        TicketWriteRequest(
            title="Updated title",
            description="updated description",
            tag_ids=[3],
        ),
    )
    assert ticket.title == "Updated title"
    assert ticket.tag_ids == [3]


def test_complete_and_reopen_ticket(ticket_service: TicketService) -> None:
    completed = ticket_service.complete_ticket(1)
    assert completed.status == "done"
    assert completed.completed_at is not None

    reopened = ticket_service.reopen_ticket(1)
    assert reopened.status == "open"
    assert reopened.completed_at is None


def test_get_ticket_raises_not_found(ticket_service: TicketService) -> None:
    with pytest.raises(AppError) as exc:
        ticket_service.get_ticket(404)
    assert exc.value.status_code == status.HTTP_404_NOT_FOUND
    assert exc.value.code == "TICKET_NOT_FOUND"


def test_list_tickets_supports_filters_and_meta(ticket_service: TicketService) -> None:
    response = ticket_service.list_tickets(
        tag_id=1,
        q="initial",
        status="open",
        page=1,
        page_size=20,
    )

    assert response.meta.page == 1
    assert response.meta.page_size == 20
    assert response.meta.total == 1
    assert len(response.data) == 1
    assert response.data[0].id == 1
