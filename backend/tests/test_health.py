"""Smoke tests for the Phase 1 API surface."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_expected_contract() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "smart-logistics-api"}


def test_database_health_is_reachable() -> None:
    response = client.get("/api/health/db")
    assert response.status_code == 200
    body = response.json()
    assert body["connected"] is True
    assert body["dialect"] in {"postgresql", "sqlite"}


def test_service_info() -> None:
    response = client.get("/api/info")
    assert response.status_code == 200
    assert response.json()["service"] == "smart-logistics-api"


def test_root_redirect_payload() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["health"] == "/api/health"


def test_sqlite_fallback_is_development_only(monkeypatch) -> None:
    """SQLite must never silently replace PostgreSQL outside development.

    Falling back in production would write stock movements to a local file while
    the real database is down, corrupting the inventory record.
    """
    from app.core.config import settings
    from app.db import session as db_session

    monkeypatch.setattr(settings, "DATABASE_FALLBACK_SQLITE", True)

    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    assert db_session.fallback_allowed() is True

    for environment in ("production", "staging", "prod"):
        monkeypatch.setattr(settings, "ENVIRONMENT", environment)
        assert db_session.fallback_allowed() is False, environment

    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "DATABASE_FALLBACK_SQLITE", False)
    assert db_session.fallback_allowed() is False


def test_postgresql_is_the_configured_target() -> None:
    """The shipped default must point at PostgreSQL, not at the fallback."""
    from app.core.config import Settings

    assert Settings.model_fields["DATABASE_URL"].default.startswith("postgresql")
