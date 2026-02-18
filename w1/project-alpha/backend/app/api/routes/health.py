from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.models.schemas.health import HealthResponse
from app.repositories.health_repository import HealthRepository
from app.services.health_service import HealthService

router = APIRouter()


def get_health_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> HealthService:
    return HealthService(
        repository=HealthRepository(),
        settings=settings,
    )


@router.get("/health", response_model=HealthResponse)
def health(
    health_service: Annotated[HealthService, Depends(get_health_service)],
) -> HealthResponse:
    return health_service.get_health()
