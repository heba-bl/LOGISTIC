"""Domain exceptions.

Services raise these; a single exception handler in ``main.py`` turns them into
HTTP responses. Business rules therefore stay expressed in business terms and no
service ever imports FastAPI.
"""

from __future__ import annotations


class DomainError(Exception):
    """Base class for every business-rule violation."""

    status_code = 400
    code = "domain_error"

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(DomainError):
    """The requested entity does not exist."""

    status_code = 404
    code = "not_found"


class ValidationError(DomainError):
    """The payload is structurally valid but breaks a business rule."""

    status_code = 422
    code = "validation_error"


class WorkflowError(DomainError):
    """The operation is not allowed from the current workflow state.

    Example: confirming storage for a lot that quality has not approved.
    """

    status_code = 409
    code = "workflow_error"


class InsufficientStockError(DomainError):
    """A stock decrement would drive the balance below zero.

    Stock can never go negative - this is enforced in the service, again by a
    CHECK constraint in the database.
    """

    status_code = 409
    code = "insufficient_stock"


class CapacityError(DomainError):
    """The target warehouse location cannot hold the requested quantity."""

    status_code = 409
    code = "insufficient_capacity"
