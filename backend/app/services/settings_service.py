"""Runtime business settings.

Business thresholds are stored in the ``system_settings`` table and read through
this service. Nothing in the codebase hardcodes the 5% reception tolerance: the
default lives here once, and can be overridden per part or from the Settings
screen.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.system import SystemSetting


@dataclass(frozen=True)
class SettingSpec:
    key: str
    default: str
    value_type: str
    label: str
    description: str
    group: str


#: Canonical catalogue of tunable business rules.
SETTING_SPECS: tuple[SettingSpec, ...] = (
    SettingSpec(
        key="reception.tolerance_percent_small",
        default="5.0",
        value_type="float",
        label="Reception tolerance - small parts (%)",
        description=(
            "Maximum accepted deviation between expected and received quantity for parts "
            "classified as SMALL. A part can override this value individually."
        ),
        group="reception",
    ),
    SettingSpec(
        key="reception.tolerance_percent_large",
        default="0.0",
        value_type="float",
        label="Reception tolerance - large parts (%)",
        description=(
            "Large parts are counted exactly: the expected quantity must match. "
            "Kept configurable so the rule can be relaxed if the business changes."
        ),
        group="reception",
    ),
    SettingSpec(
        key="inspection.sample_percent",
        default="4.0",
        value_type="float",
        label="Default sampling rate (%)",
        description="Share of a lot drawn as the inspection sample when no size is given.",
        group="inspection",
    ),
    SettingSpec(
        key="inspection.sample_minimum",
        default="5",
        value_type="int",
        label="Minimum sample size",
        description="Lower bound of the computed sample, so small lots are still checked.",
        group="inspection",
    ),
    SettingSpec(
        key="inspection.defect_threshold_percent",
        default="2.0",
        value_type="float",
        label="Defect threshold (%)",
        description=(
            "Defect rate on the sample above which the lot is declared non conform "
            "and sent to the Red Cage."
        ),
        group="inspection",
    ),
    SettingSpec(
        key="warehouse.warning_occupancy_percent",
        default="75.0",
        value_type="float",
        label="Location warning occupancy (%)",
        description="Occupancy above which a location is flagged as nearly full.",
        group="warehouse",
    ),
    SettingSpec(
        key="warehouse.critical_occupancy_percent",
        default="90.0",
        value_type="float",
        label="Location critical occupancy (%)",
        description="Occupancy above which a location is considered saturated.",
        group="warehouse",
    ),
    SettingSpec(
        key="ai.shortage_cover_days_high",
        default="2.0",
        value_type="float",
        label="Shortage risk - high (days of cover)",
        description="Days of stock cover below which shortage risk is rated HIGH.",
        group="ai",
    ),
    SettingSpec(
        key="ai.shortage_cover_days_medium",
        default="5.0",
        value_type="float",
        label="Shortage risk - medium (days of cover)",
        description="Days of stock cover below which shortage risk is rated MEDIUM.",
        group="ai",
    ),
    SettingSpec(
        key="ai.blocked_lot_hours",
        default="24.0",
        value_type="float",
        label="Blocked lot escalation (hours)",
        description="A lot blocked longer than this is escalated by the priority engine.",
        group="ai",
    ),
)

_SPECS_BY_KEY = {spec.key: spec for spec in SETTING_SPECS}


def _cast(value: str, value_type: str) -> Any:
    if value_type == "float":
        return float(value)
    if value_type == "int":
        return int(float(value))
    if value_type == "bool":
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return value


def ensure_defaults(db: Session) -> None:
    """Insert any setting that is missing. Safe to call repeatedly."""
    existing = {row for row in db.execute(select(SystemSetting.key)).scalars()}
    for spec in SETTING_SPECS:
        if spec.key in existing:
            continue
        db.add(
            SystemSetting(
                key=spec.key,
                value=spec.default,
                value_type=spec.value_type,
                label=spec.label,
                description=spec.description,
                group=spec.group,
            )
        )
    db.flush()


def get_setting(db: Session, key: str) -> Any:
    """Return a typed setting value, falling back to the declared default."""
    spec = _SPECS_BY_KEY.get(key)
    row = db.execute(select(SystemSetting).where(SystemSetting.key == key)).scalar_one_or_none()
    if row is not None:
        return _cast(row.value, row.value_type)
    if spec is None:
        raise KeyError(f"Unknown setting: {key}")
    return _cast(spec.default, spec.value_type)


def get_float(db: Session, key: str) -> float:
    return float(get_setting(db, key))


def get_int(db: Session, key: str) -> int:
    return int(get_setting(db, key))


def list_settings(db: Session) -> list[SystemSetting]:
    ensure_defaults(db)
    return list(db.execute(select(SystemSetting).order_by(SystemSetting.group, SystemSetting.key)).scalars())


def update_setting(db: Session, key: str, value: str) -> SystemSetting:
    """Update one setting after validating that the value casts correctly."""
    from app.core.exceptions import NotFoundError, ValidationError

    row = db.execute(select(SystemSetting).where(SystemSetting.key == key)).scalar_one_or_none()
    if row is None:
        raise NotFoundError(f"Unknown setting: {key}")
    try:
        _cast(value, row.value_type)
    except ValueError as exc:
        raise ValidationError(f"Value '{value}' is not a valid {row.value_type}") from exc
    row.value = value
    db.flush()
    return row
