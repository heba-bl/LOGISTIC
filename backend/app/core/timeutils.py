"""Timestamp helpers.

Timestamps are stored as UTC. SQLite returns them naive, PostgreSQL returns them
aware, so everything is normalised here before being formatted for a human.
"""

from __future__ import annotations

from datetime import datetime, timezone


def as_utc(value: datetime) -> datetime:
    """Return the value as an aware UTC datetime, assuming naive means UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def to_local(value: datetime) -> datetime:
    """Convert a stored timestamp to the server local timezone for display."""
    return as_utc(value).astimezone()


def format_local(value: datetime, pattern: str = "%d/%m %H:%M") -> str:
    """Human-readable local timestamp, used in text the operator reads."""
    return to_local(value).strftime(pattern)
