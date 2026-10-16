import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.api import api_router
from app.api.fixture import router as fixture_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure data directory exists
    os.makedirs(settings.DATA_DIR, exist_ok=True)
    # Validate encryption key and encrypted credential integrity at startup
    from app.services.security import validate_encryption_key_at_startup
    validate_encryption_key_at_startup()
    # Validate production access security at startup
    from app.services.auth import validate_production_auth_at_startup
    validate_production_auth_at_startup()
    # Ensure version_artifacts table exists if migrations have not yet run
    try:
        from app.database import engine
        from app.models.models import VersionArtifact
        VersionArtifact.__table__.create(bind=engine, checkfirst=True)
    except Exception:
        pass
    yield


is_prod = settings.ENVIRONMENT.lower() == "production"

app = FastAPI(
    title="Website Change Detector API",
    description="Backend API for autonomous website change detection and visual diffing.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None if is_prod else "/docs",
    redoc_url=None if is_prod else "/redoc",
    openapi_url=None if is_prod else "/openapi.json",
)

# CORS configuration: strict allowed origins
configured_origins = [orig.strip() for orig in (settings.ALLOWED_ORIGINS or "").split(",") if orig.strip()]
if not is_prod:
    default_dev_origins = ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000", "http://127.0.0.1:3000"]
    for d in default_dev_origins:
        if d not in configured_origins:
            configured_origins.append(d)

app.add_middleware(
    CORSMiddleware,
    allow_origins=configured_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include core API routes
app.include_router(api_router)

# Include fixture routes only in non-production environments
if not is_prod:
    app.include_router(fixture_router)


@app.get("/", tags=["Root"])
def root():
    response = {
        "name": "Website Change Detector API",
        "status": "active",
        "health_url": "/api/health",
    }
    if not is_prod:
        response["docs_url"] = "/docs"
    return response
