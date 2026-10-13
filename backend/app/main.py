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
    yield


app = FastAPI(
    title="Website Change Detector API",
    description="Backend API for autonomous website change detection and visual diffing.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS configuration for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include core API routes
app.include_router(api_router)
# Include fixture routes for deterministic local testing
app.include_router(fixture_router)


@app.get("/", tags=["Root"])
def root():
    return {
        "name": "Website Change Detector API",
        "version": "1.0.0",
        "docs_url": "/docs",
        "health_url": "/api/health",
    }
