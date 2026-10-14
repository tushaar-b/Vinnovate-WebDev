from fastapi import APIRouter
from app.api.health import router as health_router
from app.api.monitors import router as monitors_router
from app.api.notifications import router as notifications_router
from app.api.activity import router as activity_router

api_router = APIRouter(prefix="/api")
api_router.include_router(health_router)
api_router.include_router(monitors_router)
api_router.include_router(notifications_router)
api_router.include_router(activity_router)
