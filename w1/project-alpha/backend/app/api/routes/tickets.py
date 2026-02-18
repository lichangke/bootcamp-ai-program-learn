from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.models.entities import TicketStatus
from app.models.schemas.ticket import TicketDataResponse, TicketListResponse, TicketWriteRequest
from app.repositories.tag_repository import TagRepository
from app.repositories.ticket_repository import TicketRepository
from app.repositories.ticket_tag_repository import TicketTagRepository
from app.services.ticket_service import TicketService

router = APIRouter(prefix="/tickets")


def get_ticket_service() -> TicketService:
    return TicketService(
        ticket_repository=TicketRepository(),
        ticket_tag_repository=TicketTagRepository(),
        tag_repository=TagRepository(),
    )


@router.get("", response_model=TicketListResponse)
def list_tickets(
    ticket_service: Annotated[TicketService, Depends(get_ticket_service)],
    tag_id: Annotated[int | None, Query()] = None,
    q: Annotated[str | None, Query()] = None,
    status: Annotated[TicketStatus | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> TicketListResponse:
    return ticket_service.list_tickets(
        tag_id=tag_id,
        q=q,
        status=status,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=TicketDataResponse, status_code=status.HTTP_201_CREATED)
def create_ticket(
    payload: TicketWriteRequest,
    ticket_service: Annotated[TicketService, Depends(get_ticket_service)],
) -> TicketDataResponse:
    ticket = ticket_service.create_ticket(payload)
    return TicketDataResponse(data=ticket)


@router.get("/{ticket_id}", response_model=TicketDataResponse)
def get_ticket(
    ticket_id: int,
    ticket_service: Annotated[TicketService, Depends(get_ticket_service)],
) -> TicketDataResponse:
    ticket = ticket_service.get_ticket(ticket_id)
    return TicketDataResponse(data=ticket)


@router.put("/{ticket_id}", response_model=TicketDataResponse)
def update_ticket(
    ticket_id: int,
    payload: TicketWriteRequest,
    ticket_service: Annotated[TicketService, Depends(get_ticket_service)],
) -> TicketDataResponse:
    ticket = ticket_service.update_ticket(ticket_id, payload)
    return TicketDataResponse(data=ticket)


@router.delete("/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ticket(
    ticket_id: int,
    ticket_service: Annotated[TicketService, Depends(get_ticket_service)],
) -> Response:
    ticket_service.delete_ticket(ticket_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/{ticket_id}/complete", response_model=TicketDataResponse)
def complete_ticket(
    ticket_id: int,
    ticket_service: Annotated[TicketService, Depends(get_ticket_service)],
) -> TicketDataResponse:
    ticket = ticket_service.complete_ticket(ticket_id)
    return TicketDataResponse(data=ticket)


@router.patch("/{ticket_id}/reopen", response_model=TicketDataResponse)
def reopen_ticket(
    ticket_id: int,
    ticket_service: Annotated[TicketService, Depends(get_ticket_service)],
) -> TicketDataResponse:
    ticket = ticket_service.reopen_ticket(ticket_id)
    return TicketDataResponse(data=ticket)
