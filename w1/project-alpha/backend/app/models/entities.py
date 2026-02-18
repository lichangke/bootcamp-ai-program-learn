from dataclasses import dataclass
from datetime import datetime
from typing import Literal

TicketStatus = Literal["open", "done"]


@dataclass(slots=True)
class TicketEntity:
    id: int
    title: str
    description: str | None
    status: TicketStatus
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


@dataclass(slots=True)
class TagEntity:
    id: int
    name: str
    created_at: datetime
    updated_at: datetime
