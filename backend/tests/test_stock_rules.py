"""The non-negotiable stock rules.

    IN  : reception -> inspection -> quality -> storage confirmed -> STOCK +
    OUT : request -> approval -> preparation -> issue confirmed  -> STOCK -

Nothing before the final confirmation may move the balance, stock may never go
negative, and every movement must leave a StockMovement and an AuditLog.
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.core.exceptions import InsufficientStockError, ValidationError, WorkflowError
from app.models.enums import AuditAction, LotStatus, MovementType, ProductionRequestStatus
from app.models.system import AuditLog
from app.models.warehouse import StockMovement
from app.services import (
    inspection_service,
    production_service,
    quality_service,
    reception_service,
    stock_service,
    warehouse_service,
)
from app.services.warehouse_service import Allocation


def _receive(db, world, quantity: int = 100):
    return reception_service.create_reception(
        db,
        part_id=world["small"].id,
        supplier_id=world["supplier"].id,
        quantity_expected=quantity,
        quantity_received=quantity,
        actor_id=world["user"].id,
    )


def _through_quality(db, world, quantity: int = 100):
    reception = _receive(db, world, quantity)
    lot = reception.lot
    inspection_service.start_inspection(db, lot_id=lot.id, actor_id=world["user"].id)
    inspection_service.record_inspection(
        db, lot_id=lot.id, sample_size=10, defects_found=0, actor_id=world["user"].id
    )
    quality_service.approve(
        db, lot_id=lot.id, justification="conform", actor_id=world["user"].id
    )
    return lot


def _store(db, world, lot):
    return warehouse_service.confirm_storage(
        db,
        lot_id=lot.id,
        allocations=[Allocation(location_id=world["primary"].id, quantity=lot.quantity_approved)],
        actor_id=world["user"].id,
    )


# --------------------------------------------------------------------------- IN
def test_reception_does_not_create_stock(db, world):
    reception = _receive(db, world, 100)

    assert stock_service.get_available(db, world["small"].id) == 0
    assert reception.lot.status is LotStatus.PENDING_INSPECTION
    assert db.execute(select(func.count()).select_from(StockMovement)).scalar_one() == 0


def test_inspection_does_not_create_stock(db, world):
    reception = _receive(db, world, 100)
    inspection_service.start_inspection(db, lot_id=reception.lot_id, actor_id=world["user"].id)
    inspection_service.record_inspection(
        db, lot_id=reception.lot_id, sample_size=10, defects_found=0, actor_id=world["user"].id
    )

    assert stock_service.get_available(db, world["small"].id) == 0
    assert reception.lot.status is LotStatus.QUALITY_PENDING


def test_quality_approval_does_not_create_stock(db, world):
    lot = _through_quality(db, world, 100)

    assert lot.status is LotStatus.APPROVED
    assert lot.quantity_approved == 100
    assert stock_service.get_available(db, world["small"].id) == 0, (
        "approving a lot must not create stock, only unlock storage"
    )


def test_storage_confirmation_is_the_only_increment(db, world):
    lot = _through_quality(db, world, 100)
    assert stock_service.get_available(db, world["small"].id) == 0

    movements = _store(db, world, lot)

    assert stock_service.get_available(db, world["small"].id) == 100
    assert lot.status is LotStatus.STORED
    assert lot.quantity_available == 100
    assert len(movements) == 1
    assert movements[0].movement_type is MovementType.IN
    assert movements[0].quantity_before == 0
    assert movements[0].quantity_after == 100


def test_storage_refused_when_quality_has_not_approved(db, world):
    reception = _receive(db, world, 100)

    with pytest.raises(WorkflowError):
        warehouse_service.confirm_storage(
            db,
            lot_id=reception.lot_id,
            allocations=[Allocation(location_id=world["primary"].id, quantity=100)],
            actor_id=world["user"].id,
        )
    assert stock_service.get_available(db, world["small"].id) == 0


def test_storage_quantity_must_match_the_approved_quantity(db, world):
    lot = _through_quality(db, world, 100)

    with pytest.raises(ValidationError):
        warehouse_service.confirm_storage(
            db,
            lot_id=lot.id,
            allocations=[Allocation(location_id=world["primary"].id, quantity=80)],
            actor_id=world["user"].id,
        )
    assert stock_service.get_available(db, world["small"].id) == 0


def test_storage_can_be_split_across_secondary_addresses(db, world):
    lot = _through_quality(db, world, 100)

    movements = warehouse_service.confirm_storage(
        db,
        lot_id=lot.id,
        allocations=[
            Allocation(location_id=world["primary"].id, quantity=60),
            Allocation(location_id=world["secondary"].id, quantity=40),
        ],
        actor_id=world["user"].id,
    )

    assert len(movements) == 2
    assert stock_service.get_available(db, world["small"].id) == 100
    assert world["primary"].occupied == 60
    assert world["secondary"].occupied == 40


def test_storage_refused_when_location_is_too_small(db, world):
    lot = _through_quality(db, world, 100)

    from app.core.exceptions import CapacityError

    with pytest.raises(CapacityError):
        warehouse_service.confirm_storage(
            db,
            lot_id=lot.id,
            allocations=[Allocation(location_id=world["tiny"].id, quantity=100)],
            actor_id=world["user"].id,
        )
    assert stock_service.get_available(db, world["small"].id) == 0


# -------------------------------------------------------------------------- OUT
def _stocked_request(db, world, stock_quantity: int = 100, request_quantity: int = 20):
    lot = _through_quality(db, world, stock_quantity)
    _store(db, world, lot)
    request = production_service.create_request(
        db,
        station_id=world["station"].id,
        part_id=world["small"].id,
        quantity=request_quantity,
        actor_id=world["user"].id,
        submit_immediately=True,
    )
    return lot, request


def test_request_creation_does_not_decrement_stock(db, world):
    _, request = _stocked_request(db, world)

    assert stock_service.get_available(db, world["small"].id) == 100
    assert request.status is ProductionRequestStatus.SUBMITTED


def test_approval_reserves_but_does_not_decrement(db, world):
    _, request = _stocked_request(db, world)
    production_service.approve(db, request_id=request.id, actor_id=world["user"].id)

    stock = stock_service.get_or_create_stock(db, world["small"].id)
    assert stock.quantity_available == 100, "approval must not touch the available quantity"
    assert stock.quantity_reserved == 20
    assert stock.quantity_free == 80


def test_only_confirmed_issue_decrements_stock(db, world):
    _, request = _stocked_request(db, world)
    production_service.approve(db, request_id=request.id, actor_id=world["user"].id)
    production_service.start_preparation(db, request_id=request.id, actor_id=world["user"].id)
    production_service.mark_ready(db, request_id=request.id, actor_id=world["user"].id)

    assert stock_service.get_available(db, world["small"].id) == 100

    _, movement = production_service.issue(
        db, request_id=request.id, actor_id=world["user"].id
    )

    assert stock_service.get_available(db, world["small"].id) == 80
    assert movement.movement_type is MovementType.OUT
    assert movement.quantity_before == 100
    assert movement.quantity_after == 80


def test_issue_cannot_skip_the_workflow(db, world):
    _, request = _stocked_request(db, world)

    # SUBMITTED -> ISSUED is not a legal transition.
    with pytest.raises(WorkflowError):
        production_service.issue(db, request_id=request.id, actor_id=world["user"].id)
    assert stock_service.get_available(db, world["small"].id) == 100


def test_stock_can_never_go_negative(db, world):
    _, request = _stocked_request(db, world, stock_quantity=100, request_quantity=20)
    production_service.approve(db, request_id=request.id, actor_id=world["user"].id)
    production_service.start_preparation(db, request_id=request.id, actor_id=world["user"].id)
    production_service.mark_ready(db, request_id=request.id, actor_id=world["user"].id)

    with pytest.raises(InsufficientStockError):
        stock_service.decrement(
            db,
            part=world["small"],
            quantity=5000,
            request=request,
            actor=world["user"],
            reason="attempt to over-issue",
        )
    assert stock_service.get_available(db, world["small"].id) == 100


def test_cancelling_an_approved_request_releases_the_reservation(db, world):
    _, request = _stocked_request(db, world)
    production_service.approve(db, request_id=request.id, actor_id=world["user"].id)
    production_service.cancel(
        db, request_id=request.id, reason="line stopped", actor_id=world["user"].id
    )

    stock = stock_service.get_or_create_stock(db, world["small"].id)
    assert stock.quantity_reserved == 0
    assert stock.quantity_available == 100


# ------------------------------------------------------------- ledger and audit
def test_every_movement_writes_a_movement_and_an_audit_entry(db, world):
    lot = _through_quality(db, world, 100)
    _store(db, world, lot)

    movements = db.execute(select(StockMovement)).scalars().all()
    assert len(movements) == 1

    audit_actions = set(
        db.execute(select(AuditLog.action)).scalars().all()
    )
    assert AuditAction.STOCK_INCREMENTED in audit_actions
    assert AuditAction.STORAGE_CONFIRMED in audit_actions
    assert AuditAction.LOT_RECEIVED in audit_actions
    assert AuditAction.QUALITY_APPROVED in audit_actions


def test_movement_ledger_is_self_consistent(db, world):
    _, request = _stocked_request(db, world)
    production_service.approve(db, request_id=request.id, actor_id=world["user"].id)
    production_service.start_preparation(db, request_id=request.id, actor_id=world["user"].id)
    production_service.mark_ready(db, request_id=request.id, actor_id=world["user"].id)
    production_service.issue(db, request_id=request.id, actor_id=world["user"].id)

    movements = db.execute(select(StockMovement).order_by(StockMovement.id)).scalars().all()
    balance = 0
    for movement in movements:
        assert movement.quantity_before == balance
        balance += movement.quantity if movement.movement_type is MovementType.IN else -movement.quantity
        assert movement.quantity_after == balance

    assert balance == stock_service.get_available(db, world["small"].id)


def test_lot_is_consumed_when_fully_issued(db, world):
    lot, request = _stocked_request(db, world, stock_quantity=100, request_quantity=100)
    production_service.approve(db, request_id=request.id, actor_id=world["user"].id)
    production_service.start_preparation(db, request_id=request.id, actor_id=world["user"].id)
    production_service.mark_ready(db, request_id=request.id, actor_id=world["user"].id)
    production_service.issue(db, request_id=request.id, actor_id=world["user"].id)

    assert lot.quantity_available == 0
    assert lot.status is LotStatus.CONSUMED
    assert world["primary"].occupied == 0
