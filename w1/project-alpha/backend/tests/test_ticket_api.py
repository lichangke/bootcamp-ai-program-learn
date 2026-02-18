from datetime import UTC, datetime

from app.api.routes.tickets import get_ticket_service
from app.core.errors import AppError
from app.main import app
from app.models.schemas.ticket import (
    TicketListMeta,
    TicketListResponse,
    TicketRead,
    TicketWriteRequest,
)
from fastapi import status
from fastapi.testclient import TestClient


class _FakeTicketService:
    def __init__(self) -> None:
        now = datetime.now(UTC)
        self._ticket = TicketRead(
            id=1,
            title="Seed ticket",
            description="seed",
            status="open",
            tag_ids=[1],
            created_at=now,
            updated_at=now,
            completed_at=None,
        )
        self.deleted_ids: list[int] = []

    def create_ticket(self, payload: TicketWriteRequest) -> TicketRead:
        now = datetime.now(UTC)
        self._ticket = TicketRead(
            id=2,
            title=payload.title.strip(),
            description=payload.description,
            status="open",
            tag_ids=payload.tag_ids,
            created_at=now,
            updated_at=now,
            completed_at=None,
        )
        return self._ticket

    def list_tickets(
        self,
        *,
        tag_id: int | None,
        q: str | None,
        status: str | None,
        page: int,
        page_size: int,
    ) -> TicketListResponse:
        _ = (tag_id, q, status)
        return TicketListResponse(
            data=[self._ticket],
            meta=TicketListMeta(page=page, page_size=page_size, total=1),
        )

    def get_ticket(self, ticket_id: int) -> TicketRead:
        if ticket_id == 404:
            raise AppError(
                status_code=status.HTTP_404_NOT_FOUND,
                code="TICKET_NOT_FOUND",
                message="Ticket not found.",
            )
        return self._ticket

    def update_ticket(self, ticket_id: int, payload: TicketWriteRequest) -> TicketRead:
        if ticket_id == 404:
            raise AppError(
                status_code=status.HTTP_404_NOT_FOUND,
                code="TICKET_NOT_FOUND",
                message="Ticket not found.",
            )
        self._ticket = self._ticket.model_copy(
            update={
                "title": payload.title.strip(),
                "description": payload.description,
                "tag_ids": payload.tag_ids,
                "updated_at": datetime.now(UTC),
            }
        )
        return self._ticket

    def delete_ticket(self, ticket_id: int) -> None:
        if ticket_id == 404:
            raise AppError(
                status_code=status.HTTP_404_NOT_FOUND,
                code="TICKET_NOT_FOUND",
                message="Ticket not found.",
            )
        self.deleted_ids.append(ticket_id)

    def complete_ticket(self, ticket_id: int) -> TicketRead:
        if ticket_id == 404:
            raise AppError(
                status_code=status.HTTP_404_NOT_FOUND,
                code="TICKET_NOT_FOUND",
                message="Ticket not found.",
            )
        self._ticket = self._ticket.model_copy(
            update={
                "status": "done",
                "completed_at": datetime.now(UTC),
                "updated_at": datetime.now(UTC),
            }
        )
        return self._ticket

    def reopen_ticket(self, ticket_id: int) -> TicketRead:
        if ticket_id == 404:
            raise AppError(
                status_code=status.HTTP_404_NOT_FOUND,
                code="TICKET_NOT_FOUND",
                message="Ticket not found.",
            )
        self._ticket = self._ticket.model_copy(
            update={"status": "open", "completed_at": None, "updated_at": datetime.now(UTC)}
        )
        return self._ticket


def test_ticket_api_routes(client: TestClient) -> None:
    service = _FakeTicketService()
    app.dependency_overrides[get_ticket_service] = lambda: service

    list_response = client.get("/api/tickets?page=1&page_size=20")
    assert list_response.status_code == status.HTTP_200_OK
    assert list_response.json()["meta"]["total"] == 1

    create_response = client.post(
        "/api/tickets",
        json={"title": "API ticket", "description": "from test", "tag_ids": [1, 2]},
    )
    assert create_response.status_code == status.HTTP_201_CREATED
    assert create_response.json()["data"]["title"] == "API ticket"

    get_response = client.get("/api/tickets/2")
    assert get_response.status_code == status.HTTP_200_OK
    assert get_response.json()["data"]["id"] == 2

    update_response = client.put(
        "/api/tickets/2",
        json={"title": "API ticket updated", "description": "updated", "tag_ids": [2]},
    )
    assert update_response.status_code == status.HTTP_200_OK
    assert update_response.json()["data"]["tag_ids"] == [2]

    complete_response = client.patch("/api/tickets/2/complete")
    assert complete_response.status_code == status.HTTP_200_OK
    assert complete_response.json()["data"]["status"] == "done"
    assert complete_response.json()["data"]["completed_at"] is not None

    reopen_response = client.patch("/api/tickets/2/reopen")
    assert reopen_response.status_code == status.HTTP_200_OK
    assert reopen_response.json()["data"]["status"] == "open"
    assert reopen_response.json()["data"]["completed_at"] is None

    delete_response = client.delete("/api/tickets/2")
    assert delete_response.status_code == status.HTTP_204_NO_CONTENT

    app.dependency_overrides.clear()


def test_ticket_api_list_page_size_limit(client: TestClient) -> None:
    service = _FakeTicketService()
    app.dependency_overrides[get_ticket_service] = lambda: service

    response = client.get("/api/tickets?page=1&page_size=101")
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    app.dependency_overrides.clear()


def test_ticket_api_error_structure(client: TestClient) -> None:
    service = _FakeTicketService()
    app.dependency_overrides[get_ticket_service] = lambda: service

    response = client.get("/api/tickets/404")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    payload = response.json()
    assert payload["error"]["code"] == "TICKET_NOT_FOUND"
    assert isinstance(payload["error"]["details"], dict)

    app.dependency_overrides.clear()
