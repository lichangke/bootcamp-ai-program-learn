from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.models.schemas.tag import TagDataResponse, TagListResponse, TagWriteRequest
from app.repositories.tag_repository import TagRepository
from app.services.tag_service import TagService

router = APIRouter(prefix="/tags")


def get_tag_service() -> TagService:
    return TagService(tag_repository=TagRepository())


@router.get("", response_model=TagListResponse)
def list_tags(
    tag_service: Annotated[TagService, Depends(get_tag_service)],
) -> TagListResponse:
    return TagListResponse(data=tag_service.list_tags())


@router.post("", response_model=TagDataResponse, status_code=status.HTTP_201_CREATED)
def create_tag(
    payload: TagWriteRequest,
    tag_service: Annotated[TagService, Depends(get_tag_service)],
) -> TagDataResponse:
    created = tag_service.create_tag(payload)
    return TagDataResponse(data=created)


@router.put("/{tag_id}", response_model=TagDataResponse)
def update_tag(
    tag_id: int,
    payload: TagWriteRequest,
    tag_service: Annotated[TagService, Depends(get_tag_service)],
) -> TagDataResponse:
    updated = tag_service.update_tag(tag_id, payload)
    return TagDataResponse(data=updated)


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tag(
    tag_id: int,
    tag_service: Annotated[TagService, Depends(get_tag_service)],
) -> Response:
    tag_service.delete_tag(tag_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
