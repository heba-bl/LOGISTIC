"""Decision-support engine for the logistics manager.

Deliberately a transparent, deterministic model rather than a black box: every
output is computed from the live database and carries the numbers that produced
it. The specification is explicit - a recommendation is never emitted without a
justification.

Three functions, as required:
  1. shortage risk      - will a reference fail to cover the confirmed demand?
  2. prioritisation     - what should the manager handle first?
  3. optimisation       - concrete advice (secondary address, rebalancing...)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.catalog import Part
from app.models.enums import (
    LotStatus,
    RecommendationKind,
    RiskLevel,
    Severity,
)
from app.models.flow import Lot
from app.models.system import AIRecommendation
from app.repositories import (
    LotRepository,
    PartRepository,
    ProductionRepository,
    RecommendationRepository,
    WarehouseRepository,
)
from app.services import settings_service, stock_service, warehouse_service


# --------------------------------------------------------------------------- 1. risk
def stock_by_part(db: Session) -> dict[int, int]:
    """Available quantity per part, in one query."""
    from app.models.warehouse import Stock

    return {
        part_id: int(quantity or 0)
        for part_id, quantity in db.execute(
            select(Stock.part_id, Stock.quantity_available)
        ).all()
    }


def demand_by_part(db: Session) -> dict[int, int]:
    """Open, unissued demand per part, in one query."""
    from app.models.enums import ProductionRequestStatus
    from app.models.production import ProductionRequest

    return {
        part_id: int(quantity or 0)
        for part_id, quantity in db.execute(
            select(
                ProductionRequest.part_id,
                func.coalesce(
                    func.sum(
                        ProductionRequest.quantity_requested
                        - ProductionRequest.quantity_issued
                    ),
                    0,
                ),
            )
            .where(
                ProductionRequest.status.in_(
                    [
                        ProductionRequestStatus.SUBMITTED,
                        ProductionRequestStatus.APPROVED,
                        ProductionRequestStatus.PREPARING,
                        ProductionRequestStatus.READY,
                    ]
                )
            )
            .group_by(ProductionRequest.part_id)
        ).all()
    }


def incoming_by_part(db: Session) -> dict[int, int]:
    """Received but not yet stock, per part, in one query."""
    return {
        part_id: int(quantity or 0)
        for part_id, quantity in db.execute(
            select(Lot.part_id, func.coalesce(func.sum(Lot.quantity_received), 0))
            .where(
                Lot.status.in_(
                    [
                        LotStatus.PENDING_INSPECTION,
                        LotStatus.INSPECTION_IN_PROGRESS,
                        LotStatus.QUALITY_PENDING,
                        LotStatus.APPROVED,
                    ]
                )
            )
            .group_by(Lot.part_id)
        ).all()
    }


def _incoming_quantity(db: Session, part_id: int) -> int:
    """Quantity of this part already received but not yet available as stock."""
    return int(
        db.execute(
            select(func.coalesce(func.sum(Lot.quantity_received), 0)).where(
                Lot.part_id == part_id,
                Lot.status.in_(
                    [
                        LotStatus.PENDING_INSPECTION,
                        LotStatus.INSPECTION_IN_PROGRESS,
                        LotStatus.QUALITY_PENDING,
                        LotStatus.APPROVED,
                    ]
                ),
            )
        ).scalar_one()
    )


def assess_shortage_risk(
    db: Session,
    part: Part,
    *,
    stock: dict[int, int] | None = None,
    demand_map: dict[int, int] | None = None,
    incoming_map: dict[int, int] | None = None,
    thresholds: tuple[float, float] | None = None,
) -> dict:
    """Rate the shortage risk of one reference and explain the rating.

    The model compares available stock against confirmed open demand, then falls
    back on days of cover derived from average daily consumption.

    The optional maps let a caller read the three figures for the whole
    catalogue in three queries instead of three per reference; without them the
    function reads its own, so a single-part call stays a single call.
    """
    available = (
        stock.get(part.id, 0) if stock is not None else stock_service.get_available(db, part.id)
    )
    demand = (
        demand_map.get(part.id, 0)
        if demand_map is not None
        else ProductionRepository(db).demand_for_part(part.id)
    )
    incoming = (
        incoming_map.get(part.id, 0)
        if incoming_map is not None
        else _incoming_quantity(db, part.id)
    )
    projected = available - demand

    if thresholds is not None:
        high_days, medium_days = thresholds
    else:
        high_days = settings_service.get_float(db, "ai.shortage_cover_days_high")
        medium_days = settings_service.get_float(db, "ai.shortage_cover_days_medium")

    consumption = part.average_daily_consumption or 0.0
    days_of_cover = round(available / consumption, 1) if consumption > 0 else None

    reasons: list[str] = []

    if projected < 0:
        risk = RiskLevel.HIGH
        reasons.append(
            f"confirmed demand ({demand}) exceeds available stock ({available}) "
            f"by {abs(projected)} units"
        )
    elif part.safety_stock and available < part.safety_stock:
        risk = RiskLevel.HIGH
        reasons.append(
            f"stock ({available}) is below the safety level ({part.safety_stock})"
        )
    elif days_of_cover is not None and days_of_cover <= high_days:
        risk = RiskLevel.HIGH
        reasons.append(
            f"only {days_of_cover} days of cover at {consumption:g} units/day "
            f"(high-risk threshold: {high_days:g} days)"
        )
    elif days_of_cover is not None and days_of_cover <= medium_days:
        risk = RiskLevel.MEDIUM
        reasons.append(
            f"{days_of_cover} days of cover at {consumption:g} units/day "
            f"(medium-risk threshold: {medium_days:g} days)"
        )
    elif demand > 0 and projected < (part.safety_stock or 0):
        risk = RiskLevel.MEDIUM
        reasons.append(
            f"after serving the open demand ({demand}) the balance ({projected}) "
            f"would fall under the safety level ({part.safety_stock})"
        )
    else:
        risk = RiskLevel.LOW
        reasons.append(
            f"{available} units available cover the confirmed demand ({demand})"
        )

    if incoming and risk is not RiskLevel.LOW:
        reasons.append(
            f"{incoming} units are already received and could relieve the situation "
            "once inspected, approved and stored"
        )

    return {
        "part_id": part.id,
        "part_reference": part.reference,
        # Names the branch the rating rests on, so the screen can word it.
        "text_key": (
            "shortage.exceedsDemand"
            if projected < 0
            else "shortage.belowSafety"
            if part.safety_stock and available < part.safety_stock
            else "shortage.thinCover"
            if days_of_cover is not None
            else "shortage.watch"
        ),
        "designation": part.designation,
        "stock_available": available,
        "open_demand": demand,
        "safety_stock": part.safety_stock,
        "incoming_quantity": incoming,
        "projected_balance": projected,
        "days_of_cover": days_of_cover,
        "risk_level": risk,
        "rationale": "; ".join(reasons).capitalize() + ".",
    }


def shortage_risks(db: Session, *, only_at_risk: bool = False) -> list[dict]:
    """Rate every reference the warehouse actually replenishes.

    Deliberately the managed perimeter and not the whole catalogue. The
    catalogue is the vehicle's bill of materials: scoring all of it put 1 998
    references that had never been supplied on the same list as the four that
    could genuinely stop a line, and a list where one entry in five hundred
    matters is a list nobody reads twice.
    """
    parts = PartRepository(db).managed()
    # Three queries for the whole catalogue, not three per reference.
    stock = stock_by_part(db)
    demand_map = demand_by_part(db)
    incoming_map = incoming_by_part(db)
    thresholds = (
        settings_service.get_float(db, "ai.shortage_cover_days_high"),
        settings_service.get_float(db, "ai.shortage_cover_days_medium"),
    )
    results = [
        assess_shortage_risk(
            db, part, stock=stock, demand_map=demand_map,
            incoming_map=incoming_map, thresholds=thresholds,
        )
        for part in parts
    ]
    if only_at_risk:
        results = [row for row in results if row["risk_level"] is not RiskLevel.LOW]
    order = {RiskLevel.HIGH: 0, RiskLevel.MEDIUM: 1, RiskLevel.LOW: 2}
    results.sort(key=lambda row: (order[row["risk_level"]], -row["open_demand"]))
    return results


# ------------------------------------------------------------------ 2. prioritisation
def _shortage_text_key(risk: dict) -> str:
    """Which situation the rating rests on.

    The interface renders a different sentence for each, so the key follows the
    same branch the assessment took rather than being a single generic label.
    """
    if risk["open_demand"] > risk["stock_available"]:
        return "shortage.exceedsDemand"
    if risk["safety_stock"] and risk["stock_available"] < risk["safety_stock"]:
        return "shortage.belowSafety"
    if risk["days_of_cover"] is not None:
        return "shortage.thinCover"
    return "shortage.watch"


def _build(
    kind: RecommendationKind,
    *,
    severity: Severity,
    priority: int,
    title: str,
    message: str,
    rationale: str,
    action: str,
    metrics: dict,
    text_key: str | None = None,
    risk_level: RiskLevel | None = None,
    part_id: int | None = None,
    lot_id: int | None = None,
    location_code: str | None = None,
) -> AIRecommendation:
    return AIRecommendation(
        kind=kind,
        text_key=text_key,
        severity=severity,
        risk_level=risk_level,
        priority=priority,
        title=title,
        message=message,
        rationale=rationale,
        recommended_action=action,
        part_id=part_id,
        lot_id=lot_id,
        location_code=location_code,
        metrics_json=json.dumps(metrics, default=str),
    )


def analyse(db: Session) -> list[AIRecommendation]:
    """Run the full analysis and persist a fresh set of recommendations.

    Priority 1 = production at risk, 2 = lot blocked too long, 3 = saturation,
    exactly as the specification orders them.
    """
    recommendations = RecommendationRepository(db)
    recommendations.deactivate_all()

    produced: list[AIRecommendation] = []
    now = datetime.now(timezone.utc)

    # --- Priority 1: production at risk -----------------------------------
    for risk in shortage_risks(db, only_at_risk=True):
        if risk["risk_level"] is RiskLevel.HIGH:
            severity, priority = Severity.CRITICAL, 1
        else:
            severity, priority = Severity.WARNING, 2

        action = (
            f"Expedite the {risk['incoming_quantity']} units already received "
            "(inspection then quality then storage)"
            if risk["incoming_quantity"]
            else f"Trigger a supplier order for {risk['part_reference']}"
        )
        produced.append(
            _build(
                RecommendationKind.SHORTAGE_RISK,
                severity=severity,
                priority=priority,
                risk_level=risk["risk_level"],
                text_key=_shortage_text_key(risk),
                title=f"Shortage risk on {risk['part_reference']}",
                message=(
                    f"{risk['part_reference']} presents a "
                    f"{risk['risk_level'].value.lower()} risk of falling short of the "
                    f"confirmed production demand."
                ),
                rationale=risk["rationale"],
                action=action,
                metrics={
                    "stock_available": risk["stock_available"],
                    "open_demand": risk["open_demand"],
                    "safety_stock": risk["safety_stock"],
                    "incoming": risk["incoming_quantity"],
                    "projected_balance": risk["projected_balance"],
                    "days_of_cover": risk["days_of_cover"],
                },
                part_id=risk["part_id"],
            )
        )

    # --- Priority 2: lots blocked for too long ----------------------------
    blocked_hours = settings_service.get_float(db, "ai.blocked_lot_hours")
    for lot in LotRepository(db).in_stage([LotStatus.RED_CAGE]):
        reference_time = lot.updated_at or lot.received_at
        if reference_time.tzinfo is None:
            reference_time = reference_time.replace(tzinfo=timezone.utc)
        blocked_for = (now - reference_time).total_seconds() / 3600.0
        overdue = blocked_for >= blocked_hours

        produced.append(
            _build(
                RecommendationKind.BLOCKED_LOT,
                severity=Severity.CRITICAL if overdue else Severity.WARNING,
                priority=2,
                text_key="blocked.overdue" if overdue else "blocked.waiting",
                title=f"Lot {lot.lot_number} blocked in Red Cage",
                message=(
                    f"{lot.lot_number} ({lot.quantity_received} x {lot.part.reference}) "
                    f"has been quarantined for {blocked_for:.1f} hours."
                ),
                rationale=(
                    f"Reason recorded: {(lot.blocked_reason or 'not specified').rstrip('.')}. "
                    f"Escalation threshold is {blocked_hours:g} hours; this lot has been "
                    f"waiting {blocked_for:.1f} hours, immobilising "
                    f"{lot.quantity_received} units of {lot.part.reference}."
                ),
                action=(
                    "Take a quality decision: release to storage or scrap the lot"
                    if overdue
                    else "Plan the quality decision for this lot"
                ),
                metrics={
                    "hours_blocked": round(blocked_for, 1),
                    "threshold_hours": blocked_hours,
                    "quantity": lot.quantity_received,
                },
                part_id=lot.part_id,
                lot_id=lot.id,
            )
        )

    # --- Priority 3: warehouse saturation ---------------------------------
    occupancy = warehouse_service.occupancy_overview(db)
    for location in occupancy["saturated"]:
        alternatives = [
            other
            for other in WarehouseRepository(db).all_locations()
            if other.is_active and other.free_capacity > 0 and other.id != location.id
        ]
        alternatives.sort(key=lambda item: item.occupancy_percent)
        best = alternatives[0] if alternatives else None

        produced.append(
            _build(
                RecommendationKind.WAREHOUSE_SATURATION,
                severity=Severity.CRITICAL,
                priority=3,
                text_key="saturation.location",
                title=f"Location {location.code} saturated",
                message=(
                    f"{location.code} is at {location.occupancy_percent}% "
                    f"({location.occupied}/{location.capacity} units)."
                ),
                rationale=(
                    f"Occupancy {location.occupancy_percent}% exceeds the critical "
                    f"threshold of {location.critical_threshold_percent:g}%. "
                    f"Only {location.free_capacity} units of capacity remain, which "
                    "will block the next storage confirmation on this address."
                ),
                action=(
                    f"Route the next deliveries to {best.code} "
                    f"({best.free_capacity} units free, {best.occupancy_percent}% occupied)"
                    if best
                    else "Free capacity before the next delivery"
                ),
                metrics={
                    "occupancy_percent": location.occupancy_percent,
                    "free_capacity": location.free_capacity,
                    "critical_threshold": location.critical_threshold_percent,
                },
                location_code=location.code,
            )
        )

    # --- Optimisation advice ----------------------------------------------
    produced.extend(_optimisation_advice(db))

    for recommendation in produced:
        db.add(recommendation)
    db.flush()
    return produced


# -------------------------------------------------------------------- 3. optimisation
def _optimisation_advice(db: Session) -> list[AIRecommendation]:
    """Concrete logistics advice: addressing, rebalancing, watchlist."""
    advice: list[AIRecommendation] = []
    warehouses = WarehouseRepository(db)

    # a) An approved lot that will not fit its primary address.
    for lot in LotRepository(db).in_stage([LotStatus.APPROVED]):
        plan = warehouse_service.suggest_allocations(
            db, part=lot.part, quantity=lot.quantity_approved or lot.quantity_received
        )
        if len(plan) > 1:
            spread = ", ".join(
                f"{item.location.code} ({item.quantity})" for item in plan
            )
            advice.append(
                _build(
                    RecommendationKind.OPTIMIZATION,
                    severity=Severity.INFO,
                    priority=3,
                    title=f"Split storage advised for {lot.lot_number}",
                    message=(
                        f"{lot.quantity_approved or lot.quantity_received} units of "
                        f"{lot.part.reference} do not fit on a single address."
                    ),
                    rationale=(
                        f"The primary address cannot absorb the whole quantity: "
                        f"{plan[0].rationale}. Spreading over {len(plan)} addresses "
                        "avoids blocking the storage confirmation."
                    ),
                    action=f"Store as follows: {spread}",
                    metrics={
                        "quantity": lot.quantity_approved or lot.quantity_received,
                        "locations": [item.location.code for item in plan],
                    },
                    part_id=lot.part_id,
                    lot_id=lot.id,
                )
            )

    # b) Stock concentrated on a single saturated address while others are empty.
    locations = list(warehouses.all_locations())
    if locations:
        occupancies = [location.occupancy_percent for location in locations]
        spread = max(occupancies) - min(occupancies)
        if spread >= 60:
            fullest = max(locations, key=lambda item: item.occupancy_percent)
            emptiest = min(locations, key=lambda item: item.occupancy_percent)
            advice.append(
                _build(
                    RecommendationKind.OPTIMIZATION,
                    severity=Severity.INFO,
                    priority=3,
                    title="Warehouse load is unbalanced",
                    message=(
                        f"{fullest.code} is at {fullest.occupancy_percent}% while "
                        f"{emptiest.code} is at {emptiest.occupancy_percent}%."
                    ),
                    rationale=(
                        f"The occupancy spread across addresses reaches {spread:.0f} points. "
                        "An unbalanced warehouse increases picking time and brings the "
                        "saturation of the busiest address forward."
                    ),
                    action=(
                        f"Register {emptiest.code} as a secondary address for the "
                        f"references stored in {fullest.code}"
                    ),
                    metrics={
                        "spread_points": round(spread, 1),
                        "fullest": fullest.code,
                        "emptiest": emptiest.code,
                    },
                    location_code=fullest.code,
                )
            )

    # c) A reference to watch: high consumption and thin cover.
    for risk in shortage_risks(db):
        if (
            risk["risk_level"] is RiskLevel.LOW
            and risk["days_of_cover"] is not None
            and risk["days_of_cover"] <= 10
            and risk["open_demand"] > 0
        ):
            advice.append(
                _build(
                    RecommendationKind.OPTIMIZATION,
                    severity=Severity.INFO,
                    priority=3,
                    title=f"Keep {risk['part_reference']} under watch",
                    message=(
                        f"{risk['part_reference']} still covers demand but only for "
                        f"{risk['days_of_cover']} days."
                    ),
                    rationale=(
                        f"Stock {risk['stock_available']} units, open demand "
                        f"{risk['open_demand']} units, cover {risk['days_of_cover']} days. "
                        "The situation is healthy today but leaves no margin if a lot "
                        "is blocked at inspection."
                    ),
                    action="Anticipate the next replenishment for this reference",
                    metrics={
                        "days_of_cover": risk["days_of_cover"],
                        "stock": risk["stock_available"],
                    },
                    part_id=risk["part_id"],
                )
            )
    return advice


def serialise(recommendation: AIRecommendation) -> dict:
    """ORM -> API shape, decoding the metrics payload."""
    metrics: dict = {}
    if recommendation.metrics_json:
        try:
            metrics = json.loads(recommendation.metrics_json)
        except json.JSONDecodeError:
            metrics = {}
    return {
        "id": recommendation.id,
        "kind": recommendation.kind,
        "severity": recommendation.severity,
        "risk_level": recommendation.risk_level,
        "priority": recommendation.priority,
        "text_key": recommendation.text_key,
        "title": recommendation.title,
        "message": recommendation.message,
        "rationale": recommendation.rationale,
        "recommended_action": recommendation.recommended_action,
        "location_code": recommendation.location_code,
        "generated_at": recommendation.generated_at,
        "part_reference": recommendation.part.reference if recommendation.part else None,
        "lot_number": recommendation.lot.lot_number if recommendation.lot else None,
        "metrics": metrics,
    }


def build_analysis(db: Session, *, refresh: bool = True) -> dict:
    """Full AI payload for the AI Assistant screen."""
    if refresh:
        analyse(db)

    active = RecommendationRepository(db).active()
    risks = shortage_risks(db, only_at_risk=True)

    counts = {"1": 0, "2": 0, "3": 0}
    for recommendation in active:
        counts[str(recommendation.priority)] = counts.get(str(recommendation.priority), 0) + 1

    # The headline is the first sentence a manager reads, so it travels as a key
    # plus its figures rather than as a finished English sentence.
    high = [risk for risk in risks if risk["risk_level"] is RiskLevel.HIGH]
    if high:
        headline = (
            f"{len(high)} reference(s) at high shortage risk, "
            f"starting with {high[0]['part_reference']}."
        )
        headline_key = "ai.headline.shortage"
        headline_values: dict = {"count": len(high), "reference": high[0]["part_reference"]}
    elif counts["2"]:
        headline = f"{counts['2']} blocked situation(s) require a decision."
        headline_key = "ai.headline.blocked"
        headline_values = {"count": counts["2"]}
    elif counts["3"]:
        headline = "Flow is healthy; only optimisation opportunities remain."
        headline_key = "ai.headline.healthy"
        headline_values = {}
    else:
        headline = "No risk detected: stock covers the confirmed demand."
        headline_key = "ai.headline.clear"
        headline_values = {}

    return {
        "generated_at": datetime.now(timezone.utc),
        "headline": headline,
        "headline_key": headline_key,
        "headline_values": headline_values,
        "shortage_risks": risks,
        "recommendations": [serialise(item) for item in active],
        "priority_count": counts,
    }
