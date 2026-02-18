from fastapi import APIRouter

from app.api.routes.health import router as health_router
from app.api.routes.tags import router as tag_router
from app.api.routes.tickets import router as ticket_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(ticket_router, tags=["tickets"])
api_router.include_router(tag_router, tags=["tags"])
