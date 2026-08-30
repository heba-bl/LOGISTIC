"""Application settings.

All configuration is environment driven (12-factor). Values are read from the
process environment first, then from a `.env` file located either in `backend/`
or at the repository root.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
ROOT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    """Typed application settings."""

    model_config = SettingsConfigDict(
        env_file=(ROOT_DIR / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Identity -----------------------------------------------------------
    PROJECT_NAME: str = "Smart Logistics Control Center"
    SERVICE_NAME: str = "smart-logistics-api"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    API_PREFIX: str = "/api"

    # --- Server -------------------------------------------------------------
    BACKEND_HOST: str = "127.0.0.1"
    BACKEND_PORT: int = 8000

    # --- CORS ---------------------------------------------------------------
    # Comma separated list. Kept as a plain string so a value such as
    # "http://a,http://b" parses without requiring JSON in the .env file.
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    # In development the Vite dev server falls back to another port when 5173 is
    # taken, so any localhost port is accepted. Empty in production.
    ALLOWED_ORIGIN_REGEX: str = r"http://(localhost|127\.0\.0\.1):\d+"

    # --- Database -----------------------------------------------------------
    DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/smart_logistics"
    # When PostgreSQL is unreachable the app degrades to a local SQLite file so
    # that development is never blocked. Set to false to fail fast instead.
    DATABASE_FALLBACK_SQLITE: bool = True
    SQLITE_PATH: str = "dev.db"
    SQL_ECHO: bool = False

    @property
    def cors_origin_regex(self) -> str | None:
        """Regex of additional accepted origins, development only."""
        if not self.is_development:
            return None
        return self.ALLOWED_ORIGIN_REGEX or None

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    @property
    def sqlite_url(self) -> str:
        path = Path(self.SQLITE_PATH)
        if not path.is_absolute():
            path = BACKEND_DIR / path
        return f"sqlite:///{path.as_posix()}"

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT.lower() in {"dev", "development", "local"}


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (one read of the environment)."""
    return Settings()


settings = get_settings()
