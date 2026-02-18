from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field

TicketStatus = Literal["open", "done"]
TagIdList = Annotated[list[int], Field(default_factory=list)]


class TicketWriteRequest(BaseModel):
    title: str
    description: str | None = None
    tag_ids: TagIdList


class TicketRead(BaseModel):
    id: int
    title: str
    description: str | None = None
    status: TicketStatus
    tag_ids: list[int]
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None


class TicketDataResponse(BaseModel):
    data: TicketRead


class TicketListMeta(BaseModel):
    page: int
    page_size: int
    total: int


class TicketListResponse(BaseModel):
    data: list[TicketRead]
    meta: TicketListMeta
