"""Users and roles (simulated — no authentication in this project).

An operator is never anonymous: every user carries a unique employee number
(matricule), a role and a service, and that identity is attached to every action
they perform, including Excel imports and validations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Enum as SAEnum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import RoleName, Zone
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.production import ProductionStation


class Role(Base, TimestampMixin):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[RoleName] = mapped_column(
        SAEnum(RoleName, native_enum=False, length=32), unique=True, nullable=False
    )
    label: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255))
    #: True when this role may validate (check) what another operator entered.
    can_validate: Mapped[bool] = mapped_column(default=False, nullable=False)

    users: Mapped[list["User"]] = relationship(back_populates="role")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Role {self.name}>"


class User(Base, TimestampMixin):
    """An operator of the platform. Roles are simulated, not enforced by auth."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    #: Unique employee number, e.g. OP-1042. Never anonymous.
    employee_number: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=False, index=True
    )
    username: Mapped[str] = mapped_column(String(60), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    first_name: Mapped[str | None] = mapped_column(String(60))
    last_name: Mapped[str | None] = mapped_column(String(60))
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), nullable=False)
    #: Free-text service label shown in the UI.
    service: Mapped[str | None] = mapped_column(String(60), index=True)
    #: Work zone, used to route validations to the right responsible.
    zone: Mapped[Zone | None] = mapped_column(
        SAEnum(Zone, native_enum=False, length=20), index=True
    )
    station_id: Mapped[int | None] = mapped_column(ForeignKey("production_stations.id"))
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    #: SHA-256 of `MATRICULE:code:salt` for the responsibles allowed to validate.
    #: Only the digest is ever stored - here, and in the shared workbook - so a
    #: leaked database row does not hand anyone a signing code.
    validation_code_hash: Mapped[str | None] = mapped_column(String(64))

    role: Mapped["Role"] = relationship(back_populates="users")
    station: Mapped["ProductionStation | None"] = relationship(back_populates="leaders")

    @property
    def role_name(self) -> str:
        return self.role.name.value if self.role else "UNKNOWN"

    @property
    def identity(self) -> str:
        """'OP-1042 — Karim Moreau (Receptionist)', used in the audit trail."""
        label = self.role.label if self.role else "no role"
        return f"{self.employee_number} - {self.full_name} ({label})"

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User {self.employee_number} {self.username}>"
