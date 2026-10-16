from fastapi import APIRouter, Depends
from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.api.judge import router as judge_router
from app.api.monitors import router as monitors_router
from app.api.notifications import router as notifications_router
from app.api.activity import router as activity_router
from app.services.auth import require_auth

api_router = APIRouter(prefix="/api")
api_router.include_router(auth_router)
api_router.include_router(health_router)
api_router.include_router(judge_router)
api_router.include_router(monitors_router, dependencies=[Depends(require_auth)])
api_router.include_router(notifications_router, dependencies=[Depends(require_auth)])
api_router.include_router(activity_router, dependencies=[Depends(require_auth)])
