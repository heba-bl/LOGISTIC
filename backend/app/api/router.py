"""Aggregate API router.

Feature routers are registered here; `main.py` only mounts this single router
under the configured API prefix.
"""

from fastapi import APIRouter

from app.api.routes import (
    catalog,
    data_exchange,
    excel_sync,
    health,
    imports,
    insights,
    lots,
    production,
    receiving,
    reports,
    warehouse,
)

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(catalog.router)
api_router.include_router(receiving.router)
api_router.include_router(imports.router)
api_router.include_router(data_exchange.router)
api_router.include_router(excel_sync.router)
api_router.include_router(reports.router)
api_router.include_router(lots.router)
api_router.include_router(warehouse.router)
api_router.include_router(production.router)
api_router.include_router(insights.router)
