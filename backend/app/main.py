"""FastAPI application entrypoint.

Run from the `backend/` directory:

    uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import settings
from app.core.exceptions import DomainError
from app.core.logging import configure_logging, get_logger
from app.db.session import db_state

configure_logging()
logger = get_logger("app.main")


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("Starting %s v%s (%s)", settings.SERVICE_NAME, settings.VERSION, settings.ENVIRONMENT)
    logger.info("Database: %s (%s)", db_state.dialect, "fallback" if db_state.fallback else "primary")
    logger.info("CORS origins: %s", ", ".join(settings.cors_origins))
    yield
    logger.info("Shutting down %s", settings.SERVICE_NAME)


def create_app() -> FastAPI:
    application = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description=(
            "Smart Logistics Control Center API - supervision of the "
            "Supplier -> Receiving -> Inspection -> Quality -> Warehouse -> Production flow. "
            "Stock is only incremented by a confirmed storage and only decremented by a "
            "confirmed issue; every movement is audited."
        ),
        docs_url="/docs",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=settings.cors_origin_regex,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.exception_handler(DomainError)
    async def domain_error_handler(_: Request, exc: DomainError) -> JSONResponse:
        """Turn a business-rule violation into a precise HTTP response.

        Services never import FastAPI: they raise domain errors and this handler
        maps them, so the frontend always receives a stable error shape.
        """
        logger.warning("%s: %s", exc.code, exc.message)
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message, "details": exc.details},
        )

    application.include_router(api_router, prefix=settings.API_PREFIX)
    return application


app = create_app()


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    return {
        "service": settings.SERVICE_NAME,
        "docs": "/docs",
        "health": f"{settings.API_PREFIX}/health",
    }
