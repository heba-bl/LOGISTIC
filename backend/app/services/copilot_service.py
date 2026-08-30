"""Logistics Copilot: natural-language questions answered from the database.

Intent is resolved by keyword matching, then each intent runs a real query. Every
answer carries its sources, so the manager can check the figures. The Copilot
never invents a number and never answers from memory - if no intent matches, it
says so and offers what it can actually do.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.enums import LotStatus, MovementType, RiskLevel
from app.core.timeutils import format_local
from app.repositories import (
    LotRepository,
    PartRepository,
    ProductionRepository,
    StockRepository,
    WarehouseRepository,
)
from app.services import ai_service, stock_service, warehouse_service


@dataclass
class Answer:
    intent: str
    answer: str
    confidence: str
    sources: list[dict]
    suggestions: list[str]


SUGGESTIONS = [
    "What are today's priorities?",
    "Which lots are blocked?",
    "Which racks are nearly full?",
    "Is there a shortage risk?",
    "Why is BR-145 stock decreasing?",
    "What should I handle first?",
]

#: Keyword sets per intent, most specific first.
INTENTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("blocked_lots", ("blocked", "block", "red cage", "redcage", "quarantine", "bloqu")),
    ("warehouse_saturation", ("rack", "location", "saturat", "full", "occupancy", "warehouse")),
    ("shortage_risk", ("shortage", "rupture", "risk", "run out", "stockout", "cover")),
    ("priorities", ("priorit", "first", "urgent", "handle", "important", "today")),
    ("stock_trend", ("decreas", "dropping", "falling", "why", "trend", "consum")),
    ("stock_level", ("stock", "quantity", "available", "how many", "level")),
    ("production", ("production", "request", "station", "demand", "issue")),
)


def detect_intent(question: str) -> str:
    lowered = question.lower()
    for intent, keywords in INTENTS:
        if any(keyword in lowered for keyword in keywords):
            return intent
    return "unknown"


def _extract_part_reference(db: Session, question: str) -> str | None:
    """Find a part reference mentioned in the question (e.g. BR-145)."""
    candidates = re.findall(r"\b[A-Za-z]{2,4}-\d{2,4}\b", question)
    parts = PartRepository(db)
    for candidate in candidates:
        if parts.by_reference(candidate.upper()):
            return candidate.upper()
    upper = question.upper()
    for part in parts.all_active():
        if part.reference.upper() in upper:
            return part.reference
    return None


# ------------------------------------------------------------------ intent handlers
def _blocked_lots(db: Session) -> Answer:
    lots = list(LotRepository(db).in_stage([LotStatus.RED_CAGE]))
    if not lots:
        return Answer(
            "blocked_lots",
            "No lot is currently blocked. The Red Cage is empty.",
            "high",
            [{"label": "Lots in Red Cage", "value": "0"}],
            SUGGESTIONS,
        )

    lines = [
        f"- {lot.lot_number} ({lot.quantity_received} x {lot.part.reference}, "
        f"supplier {lot.supplier.name}): {lot.blocked_reason or 'no reason recorded'}"
        for lot in lots
    ]
    total = sum(lot.quantity_received for lot in lots)
    return Answer(
        "blocked_lots",
        f"{len(lots)} lot(s) are blocked in the Red Cage, immobilising {total} units:\n"
        + "\n".join(lines),
        "high",
        [
            {"label": "Blocked lots", "value": str(len(lots))},
            {"label": "Units immobilised", "value": str(total)},
        ],
        SUGGESTIONS,
    )


def _warehouse_saturation(db: Session) -> Answer:
    overview = warehouse_service.occupancy_overview(db)
    saturated = overview["saturated"]
    nearly = overview["nearly_full"]

    if not saturated and not nearly:
        return Answer(
            "warehouse_saturation",
            f"No location is under pressure. Global occupancy is "
            f"{overview['occupancy_percent']}%.",
            "high",
            [{"label": "Global occupancy", "value": f"{overview['occupancy_percent']}%"}],
            SUGGESTIONS,
        )

    parts_list = []
    if saturated:
        parts_list.append(
            "Saturated: "
            + ", ".join(f"{loc.code} ({loc.occupancy_percent}%)" for loc in saturated)
        )
    if nearly:
        parts_list.append(
            "Nearly full: "
            + ", ".join(f"{loc.code} ({loc.occupancy_percent}%)" for loc in nearly)
        )

    return Answer(
        "warehouse_saturation",
        f"Global occupancy is {overview['occupancy_percent']}%. " + " ".join(parts_list) + ".",
        "high",
        [
            {"label": "Global occupancy", "value": f"{overview['occupancy_percent']}%"},
            {"label": "Saturated locations", "value": str(len(saturated))},
            {"label": "Critical threshold", "value": f"{overview['critical_threshold']:g}%"},
        ],
        SUGGESTIONS,
    )


def _shortage_risk(db: Session, question: str) -> Answer:
    reference = _extract_part_reference(db, question)
    if reference:
        part = PartRepository(db).by_reference(reference)
        risk = ai_service.assess_shortage_risk(db, part)
        return Answer(
            "shortage_risk",
            f"{reference}: {risk['risk_level'].value} risk. {risk['rationale']}",
            "high",
            [
                {"label": "Stock available", "value": str(risk["stock_available"])},
                {"label": "Open demand", "value": str(risk["open_demand"])},
                {"label": "Incoming (not yet stock)", "value": str(risk["incoming_quantity"])},
                {
                    "label": "Days of cover",
                    "value": str(risk["days_of_cover"]) if risk["days_of_cover"] else "n/a",
                },
            ],
            SUGGESTIONS,
        )

    risks = ai_service.shortage_risks(db, only_at_risk=True)
    if not risks:
        return Answer(
            "shortage_risk",
            "No shortage risk detected: every reference covers its confirmed demand.",
            "high",
            [{"label": "References at risk", "value": "0"}],
            SUGGESTIONS,
        )

    lines = [
        f"- {risk['part_reference']} ({risk['risk_level'].value}): {risk['rationale']}"
        for risk in risks[:5]
    ]
    high = [risk for risk in risks if risk["risk_level"] is RiskLevel.HIGH]
    return Answer(
        "shortage_risk",
        f"{len(risks)} reference(s) at risk, including {len(high)} at high risk:\n"
        + "\n".join(lines),
        "high",
        [
            {"label": "High risk", "value": str(len(high))},
            {"label": "Medium risk", "value": str(len(risks) - len(high))},
        ],
        SUGGESTIONS,
    )


def _priorities(db: Session) -> Answer:
    analysis = ai_service.build_analysis(db, refresh=True)
    recommendations = analysis["recommendations"][:5]

    if not recommendations:
        return Answer(
            "priorities",
            "Nothing urgent. The flow is running normally and stock covers the demand.",
            "high",
            [{"label": "Active recommendations", "value": "0"}],
            SUGGESTIONS,
        )

    lines = [
        f"{index}. [P{item['priority']}] {item['title']} - {item['recommended_action']}\n"
        f"   Why: {item['rationale']}"
        for index, item in enumerate(recommendations, start=1)
    ]
    return Answer(
        "priorities",
        f"{analysis['headline']}\n\nHandle in this order:\n" + "\n".join(lines),
        "high",
        [
            {"label": "Priority 1", "value": str(analysis["priority_count"].get("1", 0))},
            {"label": "Priority 2", "value": str(analysis["priority_count"].get("2", 0))},
            {"label": "Priority 3", "value": str(analysis["priority_count"].get("3", 0))},
        ],
        SUGGESTIONS,
    )


def _stock_trend(db: Session, question: str) -> Answer:
    reference = _extract_part_reference(db, question)
    if not reference:
        return Answer(
            "stock_trend",
            "Tell me which reference you want to analyse, for example "
            "'Why is BR-145 stock decreasing?'.",
            "low",
            [],
            SUGGESTIONS,
        )

    part = PartRepository(db).by_reference(reference)
    movements = StockRepository(db).movements(part_id=part.id, limit=20)
    outs = [m for m in movements if m.movement_type is MovementType.OUT]
    ins = [m for m in movements if m.movement_type is MovementType.IN]
    total_out = sum(m.quantity for m in outs)
    total_in = sum(m.quantity for m in ins)
    available = stock_service.get_available(db, part.id)

    if not movements:
        return Answer(
            "stock_trend",
            f"{reference} has no recorded movement yet. Current stock: {available} units.",
            "high",
            [{"label": "Stock", "value": str(available)}],
            SUGGESTIONS,
        )

    detail = "\n".join(
        f"- {format_local(m.occurred_at)} {m.movement_type.value} {m.quantity} "
        f"({m.reason or 'no reason recorded'})"
        for m in outs[:5]
    )
    trend = "decreasing" if total_out > total_in else "increasing" if total_in > total_out else "stable"

    return Answer(
        "stock_trend",
        f"{reference} stock is {trend}: {total_in} units in and {total_out} units out "
        f"over the last {len(movements)} movements, current balance {available} units.\n"
        f"Most recent issues:\n{detail or '- no issue recorded'}",
        "high",
        [
            {"label": "Current stock", "value": str(available)},
            {"label": "Total in", "value": str(total_in)},
            {"label": "Total out", "value": str(total_out)},
        ],
        SUGGESTIONS,
    )


def _stock_level(db: Session, question: str) -> Answer:
    reference = _extract_part_reference(db, question)
    stocks = StockRepository(db)

    if reference:
        part = PartRepository(db).by_reference(reference)
        available = stock_service.get_available(db, part.id)
        demand = ProductionRepository(db).demand_for_part(part.id)
        links = WarehouseRepository(db).part_links(part.id)
        addresses = ", ".join(f"{link.location.code} ({link.role.value.lower()})" for link in links)
        return Answer(
            "stock_level",
            f"{reference}: {available} units available, {demand} committed to open "
            f"production requests. Addresses: {addresses or 'none registered'}.",
            "high",
            [
                {"label": "Available", "value": str(available)},
                {"label": "Open demand", "value": str(demand)},
                {"label": "Safety stock", "value": str(part.safety_stock)},
            ],
            SUGGESTIONS,
        )

    total = stocks.total_quantity()
    rows = stocks.all_with_parts()
    top = sorted(rows, key=lambda row: row.quantity_available, reverse=True)[:5]
    detail = "\n".join(
        f"- {row.part.reference}: {row.quantity_available} units" for row in top
    )
    return Answer(
        "stock_level",
        f"Total stock is {total} units across {len(rows)} references. Largest holdings:\n{detail}",
        "high",
        [
            {"label": "Total stock", "value": str(total)},
            {"label": "References", "value": str(len(rows))},
        ],
        SUGGESTIONS,
    )


def _production(db: Session) -> Answer:
    production = ProductionRepository(db)
    open_requests = list(production.open_requests())

    if not open_requests:
        return Answer(
            "production",
            "No production request is currently open.",
            "high",
            [{"label": "Open requests", "value": "0"}],
            SUGGESTIONS,
        )

    lines = []
    blocked = 0
    for request in open_requests[:6]:
        available = stock_service.get_available(db, request.part_id)
        covered = available >= request.quantity_requested
        if not covered:
            blocked += 1
        lines.append(
            f"- {request.reference} ({request.station.code}): "
            f"{request.quantity_requested} x {request.part.reference}, status "
            f"{request.status.value}, stock {available} "
            f"({'covered' if covered else 'NOT covered'})"
        )

    return Answer(
        "production",
        f"{len(open_requests)} open request(s), {blocked} not covered by stock:\n"
        + "\n".join(lines),
        "high",
        [
            {"label": "Open requests", "value": str(len(open_requests))},
            {"label": "Not covered", "value": str(blocked)},
        ],
        SUGGESTIONS,
    )


def _unknown() -> Answer:
    return Answer(
        "unknown",
        "I could not map that question to the data I hold. I can answer about: "
        "current priorities, blocked lots, warehouse saturation, shortage risk, "
        "stock levels and why a reference is moving.",
        "low",
        [],
        SUGGESTIONS,
    )


def ask(db: Session, question: str) -> dict:
    """Answer a question using only what the database contains."""
    intent = detect_intent(question)

    if intent == "blocked_lots":
        answer = _blocked_lots(db)
    elif intent == "warehouse_saturation":
        answer = _warehouse_saturation(db)
    elif intent == "shortage_risk":
        answer = _shortage_risk(db, question)
    elif intent == "priorities":
        answer = _priorities(db)
    elif intent == "stock_trend":
        answer = _stock_trend(db, question)
    elif intent == "stock_level":
        answer = _stock_level(db, question)
    elif intent == "production":
        answer = _production(db)
    else:
        answer = _unknown()

    return {
        "question": question,
        "intent": answer.intent,
        "answer": answer.answer,
        "confidence": answer.confidence,
        "sources": answer.sources,
        "suggestions": answer.suggestions,
        "generated_at": datetime.now(timezone.utc),
    }
