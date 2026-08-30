"""Reception tolerance, sampling, quality routing and workflow guards."""

from __future__ import annotations

import pytest

from app.core.exceptions import ValidationError, WorkflowError
from app.models.enums import (
    InspectionResult,
    LotStatus,
    ProductionRequestStatus,
    ReceptionStatus,
)
from app.services import (
    inspection_service,
    production_service,
    quality_service,
    reception_service,
    settings_service,
)


def _receive(db, world, part, expected: int, received: int):
    return reception_service.create_reception(
        db,
        part_id=part.id,
        supplier_id=world["supplier"].id,
        quantity_expected=expected,
        quantity_received=received,
        actor_id=world["user"].id,
    )


# ------------------------------------------------------- reception tolerance
def test_exact_quantity_is_accepted(db, world):
    reception = _receive(db, world, world["small"], 100, 100)
    assert reception.status is ReceptionStatus.ACCEPTED
    assert reception.quantity_gap == 0
    assert reception.lot.status is LotStatus.PENDING_INSPECTION


def test_small_part_accepts_the_default_five_percent(db, world):
    # 5% of 100 = 5 units tolerated.
    reception = _receive(db, world, world["small"], 100, 96)
    assert reception.status is ReceptionStatus.ACCEPTED_WITH_TOLERANCE
    assert reception.tolerance_percent_applied == 5.0
    assert reception.lot.status is LotStatus.PENDING_INSPECTION


def test_small_part_beyond_tolerance_goes_to_red_cage(db, world):
    reception = _receive(db, world, world["small"], 100, 90)
    assert reception.status is ReceptionStatus.QUANTITY_MISMATCH
    assert reception.lot.status is LotStatus.RED_CAGE
    assert "tolerance" in (reception.lot.blocked_reason or "").lower()


def test_large_part_requires_an_exact_quantity(db, world):
    reception = _receive(db, world, world["large"], 100, 99)
    assert reception.status is ReceptionStatus.QUANTITY_MISMATCH
    assert reception.tolerance_percent_applied == 0.0
    assert reception.lot.status is LotStatus.RED_CAGE


def test_part_level_tolerance_overrides_the_global_setting(db, world):
    # OV-300 carries its own 10% tolerance.
    reception = _receive(db, world, world["override"], 100, 92)
    assert reception.status is ReceptionStatus.ACCEPTED_WITH_TOLERANCE
    assert reception.tolerance_percent_applied == 10.0


def test_tolerance_is_configurable_not_hardcoded(db, world):
    settings_service.update_setting(db, "reception.tolerance_percent_small", "20")

    reception = _receive(db, world, world["small"], 100, 85)
    assert reception.status is ReceptionStatus.ACCEPTED_WITH_TOLERANCE
    assert reception.tolerance_percent_applied == 20.0


def test_reception_rejects_a_non_positive_expected_quantity(db, world):
    with pytest.raises(ValidationError):
        _receive(db, world, world["small"], 0, 0)


# -------------------------------------------------------------- sampling rules
def test_sample_size_respects_the_configured_rate_and_floor(db, world):
    reception = _receive(db, world, world["small"], 1000, 1000)
    # 4% of 1000 = 40, above the minimum of 5.
    assert inspection_service.suggest_sample_size(db, reception.lot) == 40

    small_reception = _receive(db, world, world["small"], 20, 20)
    # 4% of 20 = 0.8 -> ceil 1, raised to the minimum of 5.
    assert inspection_service.suggest_sample_size(db, small_reception.lot) == 5


def test_sample_size_never_exceeds_the_lot(db, world):
    reception = _receive(db, world, world["small"], 3, 3)
    assert inspection_service.suggest_sample_size(db, reception.lot) == 3


def test_conform_inspection_moves_the_lot_to_quality(db, world):
    reception = _receive(db, world, world["small"], 200, 200)
    inspection_service.start_inspection(db, lot_id=reception.lot_id, actor_id=world["user"].id)
    inspection = inspection_service.record_inspection(
        db, lot_id=reception.lot_id, sample_size=20, defects_found=0, actor_id=world["user"].id
    )

    assert inspection.result is InspectionResult.CONFORM
    assert reception.lot.status is LotStatus.QUALITY_PENDING


def test_non_conform_inspection_sends_the_lot_to_red_cage(db, world):
    reception = _receive(db, world, world["small"], 200, 200)
    inspection_service.start_inspection(db, lot_id=reception.lot_id, actor_id=world["user"].id)
    # 2 defects on 20 = 10%, above the 2% threshold.
    inspection = inspection_service.record_inspection(
        db, lot_id=reception.lot_id, sample_size=20, defects_found=2, actor_id=world["user"].id
    )

    assert inspection.result is InspectionResult.NON_CONFORM
    assert reception.lot.status is LotStatus.RED_CAGE
    assert "non conform" in (reception.lot.blocked_reason or "").lower()


def test_defects_cannot_exceed_the_sample(db, world):
    reception = _receive(db, world, world["small"], 200, 200)
    inspection_service.start_inspection(db, lot_id=reception.lot_id, actor_id=world["user"].id)

    with pytest.raises(ValidationError):
        inspection_service.record_inspection(
            db,
            lot_id=reception.lot_id,
            sample_size=10,
            defects_found=11,
            actor_id=world["user"].id,
        )


def test_inspection_cannot_start_twice(db, world):
    reception = _receive(db, world, world["small"], 100, 100)
    inspection_service.start_inspection(db, lot_id=reception.lot_id, actor_id=world["user"].id)

    with pytest.raises(WorkflowError):
        inspection_service.start_inspection(
            db, lot_id=reception.lot_id, actor_id=world["user"].id
        )


# ---------------------------------------------------------------- Red Cage flow
def _to_red_cage(db, world):
    reception = _receive(db, world, world["small"], 200, 200)
    inspection_service.start_inspection(db, lot_id=reception.lot_id, actor_id=world["user"].id)
    inspection_service.record_inspection(
        db, lot_id=reception.lot_id, sample_size=20, defects_found=5, actor_id=world["user"].id
    )
    return reception.lot


def test_red_cage_lot_can_be_released_after_a_decision(db, world):
    lot = _to_red_cage(db, world)
    assert lot.status is LotStatus.RED_CAGE

    quality_service.approve(
        db,
        lot_id=lot.id,
        justification="Defects cosmetic only, derogation granted",
        quantity_approved=180,
        actor_id=world["user"].id,
    )

    assert lot.status is LotStatus.APPROVED
    assert lot.quantity_approved == 180
    assert lot.blocked_reason is None


def test_red_cage_lot_can_be_scrapped(db, world):
    lot = _to_red_cage(db, world)
    quality_service.scrap(
        db, lot_id=lot.id, justification="Unusable parts", actor_id=world["user"].id
    )

    assert lot.status is LotStatus.REJECTED
    assert lot.quantity_approved == 0


def test_quality_decision_requires_a_justification(db, world):
    lot = _to_red_cage(db, world)
    with pytest.raises(ValidationError):
        quality_service.approve(db, lot_id=lot.id, justification="   ", actor_id=world["user"].id)


def test_approved_quantity_cannot_exceed_the_received_quantity(db, world):
    reception = _receive(db, world, world["small"], 100, 100)
    inspection_service.start_inspection(db, lot_id=reception.lot_id, actor_id=world["user"].id)
    inspection_service.record_inspection(
        db, lot_id=reception.lot_id, sample_size=10, defects_found=0, actor_id=world["user"].id
    )

    with pytest.raises(ValidationError):
        quality_service.approve(
            db,
            lot_id=reception.lot_id,
            justification="over-approval attempt",
            quantity_approved=150,
            actor_id=world["user"].id,
        )


# ------------------------------------------------------- production transitions
def _request(db, world, quantity: int = 10):
    return production_service.create_request(
        db,
        station_id=world["station"].id,
        part_id=world["small"].id,
        quantity=quantity,
        actor_id=world["user"].id,
    )


def test_request_starts_as_draft(db, world):
    request = _request(db, world)
    assert request.status is ProductionRequestStatus.DRAFT


def test_a_draft_cannot_be_approved_directly(db, world):
    request = _request(db, world)
    with pytest.raises(WorkflowError):
        production_service.approve(db, request_id=request.id, actor_id=world["user"].id)


def test_a_rejected_request_is_terminal(db, world):
    request = _request(db, world)
    production_service.submit(db, request_id=request.id, actor_id=world["user"].id)
    production_service.reject(
        db, request_id=request.id, reason="not justified", actor_id=world["user"].id
    )

    with pytest.raises(WorkflowError):
        production_service.approve(db, request_id=request.id, actor_id=world["user"].id)


def test_rejection_requires_a_reason(db, world):
    request = _request(db, world)
    production_service.submit(db, request_id=request.id, actor_id=world["user"].id)
    with pytest.raises(ValidationError):
        production_service.reject(db, request_id=request.id, reason="", actor_id=world["user"].id)


def test_priority_must_be_valid(db, world):
    with pytest.raises(ValidationError):
        production_service.create_request(
            db,
            station_id=world["station"].id,
            part_id=world["small"].id,
            quantity=10,
            priority=9,
            actor_id=world["user"].id,
        )


# ---------------------------------------------------- the managed perimeter
def test_a_reference_outside_the_perimeter_is_never_at_risk(db, world):
    """The catalogue is a bill of materials, not a stock perimeter.

    A reference the warehouse does not hold is not "short": nobody replenishes
    it. Counting it as a risk is how 1 998 references once buried the four that
    could genuinely stop a line.
    """
    from app.models.catalog import Part
    from app.services import ai_service

    unmanaged = Part(
        reference="BOM-ONLY-1",
        designation="Piece livree en kit, jamais magasinee",
        size_class=world["small"].size_class,
        is_managed=False,
        safety_stock=0,
        average_daily_consumption=0.0,
    )
    db.add(unmanaged)
    db.flush()

    references = {row["part_reference"] for row in ai_service.shortage_risks(db)}
    assert "BOM-ONLY-1" not in references


def test_a_managed_reference_is_assessed(db, world):
    """The perimeter is a filter, not a way of hiding a real shortage."""
    from app.services import ai_service

    world["small"].is_managed = True
    world["small"].safety_stock = 500
    db.flush()

    rows = {row["part_reference"]: row for row in ai_service.shortage_risks(db)}
    assert world["small"].reference in rows
    assert rows[world["small"].reference]["risk_level"].value == "HIGH"


def test_the_seeded_perimeter_stays_small_and_supplied():
    """The demonstration perimeter must be a plant's, not a catalogue's."""
    from scripts.seed import MANAGED_SCOPE_SIZE, choose_managed_scope
    from app.services import whap_source

    catalogue = whap_source.load_catalogue()
    scope = choose_managed_scope(catalogue)

    assert len(scope) == MANAGED_SCOPE_SIZE
    assert len(scope) < len(catalogue) / 10, "un perimetre n'est pas un catalogue"
    # Deterministic: two demonstrations must not disagree.
    assert scope == choose_managed_scope(catalogue)
    # Every family of the vehicle is represented, so the perimeter is not a
    # slice of the alphabet.
    systems = {a.system for a in catalogue if a.code in scope}
    assert len(systems) > 10, systems
