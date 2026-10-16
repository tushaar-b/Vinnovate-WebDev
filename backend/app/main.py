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
    # Ensure database tables and columns exist even if migration executes concurrently
    try:
        from sqlalchemy import text
        from app.database import engine
        from app.models.models import VersionArtifact
        VersionArtifact.__table__.create(bind=engine, checkfirst=True)
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE monitors ADD COLUMN IF NOT EXISTS judge_session_id VARCHAR(64);"))
            conn.execute(text("ALTER TABLE monitors ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;"))
            conn.execute(text("ALTER TABLE monitors ADD COLUMN IF NOT EXISTS manual_checks_count INTEGER DEFAULT 0 NOT NULL;"))
            conn.execute(text("ALTER TABLE monitors ADD COLUMN IF NOT EXISTS manual_checks_window_start TIMESTAMPTZ;"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_monitors_judge_session_id ON monitors (judge_session_id);"))
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

prod_origin = "https://vinnovate-web-dev.vercel.app"
if prod_origin not in configured_origins:
    configured_origins.append(prod_origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=configured_origins,
    allow_origin_regex=r"^https:\/\/.*\.vercel\.app$",
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
