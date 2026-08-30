"""Health & readiness endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings
from app.db import session as db_session
from app.schemas.health import DatabaseHealthResponse, HealthResponse, ServiceInfoResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="Liveness probe")
def health() -> HealthResponse:
    """Primary health check consumed by the frontend."""
    return HealthResponse(status="ok", service=settings.SERVICE_NAME)


@router.get("/health/db", response_model=DatabaseHealthResponse, summary="Database readiness")
def health_db() -> DatabaseHealthResponse:
    """Report which database backend is actually serving the application."""
    state = db_session.db_state
    connected = db_session.ping()
    return DatabaseHealthResponse(
        status="ok" if connected else "unavailable",
        dialect=state.dialect,
        url=state.safe_url,
        connected=connected,
        fallback=state.fallback,
        detail=state.error,
    )


@router.get("/info", response_model=ServiceInfoResponse, summary="Service metadata")
def info() -> ServiceInfoResponse:
    return ServiceInfoResponse(
        service=settings.SERVICE_NAME,
        project=settings.PROJECT_NAME,
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
        api_prefix=settings.API_PREFIX,
    )
