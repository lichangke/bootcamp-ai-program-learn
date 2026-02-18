from datetime import datetime

from pydantic import BaseModel


class TagWriteRequest(BaseModel):
    name: str


class TagRead(BaseModel):
    id: int
    name: str
    created_at: datetime
    updated_at: datetime


class TagDataResponse(BaseModel):
    data: TagRead


class TagListResponse(BaseModel):
    data: list[TagRead]
