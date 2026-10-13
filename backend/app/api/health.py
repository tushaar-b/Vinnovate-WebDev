from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from app.schemas.health import HealthResponse
from app.database import check_database_connection
from app.redis_client import check_redis_connection

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service Health Check",
    description="Returns connectivity status for the API, PostgreSQL database, and Redis.",
)
def get_health():
    db_ok = check_database_connection()
    redis_ok = check_redis_connection()

    all_healthy = db_ok and redis_ok

    payload = {
        "status": "ok" if all_healthy else "error",
        "database": "ok" if db_ok else "error",
        "redis": "ok" if redis_ok else "error",
    }

    status_code = status.HTTP_200_OK if all_healthy else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(content=payload, status_code=status_code)
