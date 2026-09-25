from fastapi import APIRouter

from app.api.routes.districts import router as districts_router
from app.api.routes.health import router as health_router
from app.api.routes.map import router as map_router
from app.api.routes.search import router as search_router

api_router = APIRouter()
api_router.include_router(health_router, prefix="/health", tags=["health"])
api_router.include_router(districts_router, tags=["districts"])
api_router.include_router(map_router, tags=["map"])
api_router.include_router(search_router, tags=["search"])
