"""Pydantic schemas for the health endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Contract consumed by the frontend status indicator."""

    status: str = Field(examples=["ok"])
    service: str = Field(examples=["smart-logistics-api"])


class DatabaseHealthResponse(BaseModel):
    """Detailed database diagnostics (development aid)."""

    status: str
    dialect: str
    url: str
    connected: bool
    fallback: bool
    detail: str | None = None


class ServiceInfoResponse(BaseModel):
    """Static service metadata."""

    service: str
    project: str
    version: str
    environment: str
    api_prefix: str
