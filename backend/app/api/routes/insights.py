"""Mission Control, traceability, analytics, AI and simulation endpoints."""

from __future__ import annotations

import json
from datetime import date

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.repositories import RecommendationRepository
from app.schemas.dashboard import (
    AiAnalysisOut,
    AnalyticsOut,
    AuditEntryOut,
    CopilotAnswer,
    CopilotQuery,
    DashboardOut,
    LotTraceOut,
    PowerBiCatalog,
    RecommendationOut,
    ShortageRiskOut,
    SimulationRequest,
    SimulationRunOut,
)
from app.schemas.overview import OverviewOut
from app.schemas.warehouse import MovementOut
from app.services import (
    ai_service,
    analytics_service,
    copilot_service,
    dashboard_service,
    overview_service,
    simulation_service,
    traceability_service,
)

router = APIRouter(tags=["insights"])


# ------------------------------------------------------------------- dashboard
@router.get("/dashboard", response_model=DashboardOut, summary="Mission Control payload")
def dashboard(db: Session = Depends(get_session)) -> DashboardOut:
    payload = dashboard_service.build_dashboard(db)
    db.commit()
    return DashboardOut.model_validate(payload)


# ---------------------------------------------------------------- traceability
@router.get(
    "/traceability/lots/{lot_id}",
    response_model=LotTraceOut,
    summary="Complete history of a lot",
)
def lot_trace(lot_id: int, db: Session = Depends(get_session)) -> LotTraceOut:
    return LotTraceOut.model_validate(traceability_service.lot_trace(db, lot_id))


@router.get(
    "/traceability/lot-number/{lot_number}",
    response_model=LotTraceOut,
    summary="Complete history of a lot by its number",
)
def lot_trace_by_number(lot_number: str, db: Session = Depends(get_session)) -> LotTraceOut:
    return LotTraceOut.model_validate(traceability_service.trace_by_lot_number(db, lot_number))


@router.get(
    "/traceability/audit", response_model=list[AuditEntryOut], summary="Search the audit trail"
)
def audit_search(
    search: str | None = None,
    entity_type: str | None = None,
    part_id: int | None = None,
    limit: int = Query(default=200, le=1000),
    db: Session = Depends(get_session),
) -> list[AuditEntryOut]:
    entries = traceability_service.search_audit(
        db, search=search, entity_type=entity_type, part_id=part_id, limit=limit
    )
    return [
        AuditEntryOut.model_validate(
            {**entry.__dict__, "action": entry.action.value}
        )
        for entry in entries
    ]


@router.get(
    "/traceability/parts/{part_id}/movements",
    response_model=list[MovementOut],
    summary="Stock history of one reference",
)
def part_movements(
    part_id: int, limit: int = Query(default=200, le=1000), db: Session = Depends(get_session)
) -> list[MovementOut]:
    return [
        MovementOut.model_validate(movement)
        for movement in traceability_service.part_history(db, part_id, limit=limit)
    ]


# -------------------------------------------------------------------- analytics
@router.get("/analytics", response_model=AnalyticsOut, summary="Analytical indicators")
def analytics(db: Session = Depends(get_session)) -> AnalyticsOut:
    return AnalyticsOut.model_validate(analytics_service.build_analytics(db))


@router.get(
    "/analytics/overview",
    response_model=OverviewOut,
    summary="Vue Logistique: indicateurs, risques et decisions",
)
def analytics_overview(
    period: str = Query(default="7d", description="today | 7d | 30d | custom"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Session = Depends(get_session),
) -> OverviewOut:
    """The decision payload behind the Logistics Overview screen.

    One request per screen rather than a dozen: every block is computed from the
    same window, so the KPI, the charts and the priority list can never disagree
    with each other.
    """
    return OverviewOut.model_validate(
        overview_service.build_overview(
            db, period=period, date_from=date_from, date_to=date_to
        )
    )


@router.get(
    "/analytics/powerbi",
    response_model=PowerBiCatalog,
    summary="Flat datasets and measures for Power BI",
)
def powerbi(db: Session = Depends(get_session)) -> PowerBiCatalog:
    return PowerBiCatalog.model_validate(analytics_service.powerbi_datasets(db))


@router.get(
    "/analytics/powerbi/theme.json",
    summary="Theme Power BI aux couleurs de SLCC",
)
def powerbi_theme() -> Response:
    """The Power BI theme file, downloadable straight into the report."""
    return Response(
        content=json.dumps(analytics_service.powerbi_theme(), indent=2),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="SLCC.json"'},
    )


# --------------------------------------------------------------------------- AI
@router.get("/ai/analysis", response_model=AiAnalysisOut, summary="Full AI analysis")
def ai_analysis(
    refresh: bool = Query(default=True), db: Session = Depends(get_session)
) -> AiAnalysisOut:
    payload = ai_service.build_analysis(db, refresh=refresh)
    db.commit()
    return AiAnalysisOut.model_validate(payload)


@router.get(
    "/ai/recommendations",
    response_model=list[RecommendationOut],
    summary="Active recommendations",
)
def ai_recommendations(db: Session = Depends(get_session)) -> list[RecommendationOut]:
    items = RecommendationRepository(db).active()
    return [RecommendationOut.model_validate(ai_service.serialise(item)) for item in items]


@router.get(
    "/ai/shortage-risk",
    response_model=list[ShortageRiskOut],
    summary="Shortage risk per reference",
)
def shortage_risk(
    only_at_risk: bool = Query(default=False), db: Session = Depends(get_session)
) -> list[ShortageRiskOut]:
    return [
        ShortageRiskOut.model_validate(row)
        for row in ai_service.shortage_risks(db, only_at_risk=only_at_risk)
    ]


@router.post("/ai/copilot", response_model=CopilotAnswer, summary="Ask the Logistics Copilot")
def copilot(payload: CopilotQuery, db: Session = Depends(get_session)) -> CopilotAnswer:
    answer = copilot_service.ask(db, payload.question)
    db.commit()
    return CopilotAnswer.model_validate(answer)


@router.get(
    "/ai/copilot/suggestions", response_model=list[str], summary="Suggested Copilot questions"
)
def copilot_suggestions() -> list[str]:
    return copilot_service.SUGGESTIONS


# -------------------------------------------------------------------- simulation
@router.post(
    "/simulation/run",
    response_model=SimulationRunOut,
    summary="Run the end-to-end demonstration scenario",
)
def run_simulation(
    payload: SimulationRequest | None = None, db: Session = Depends(get_session)
) -> SimulationRunOut:
    payload = payload or SimulationRequest()
    result = simulation_service.run_scenario(
        db,
        part_id=payload.part_id,
        supplier_id=payload.supplier_id,
        station_id=payload.station_id,
        quantity=payload.quantity,
        production_quantity=payload.production_quantity,
        stop_after=payload.stop_after,
    )
    db.commit()
    return SimulationRunOut.model_validate(result)


@router.get("/simulation/state", summary="Current state a demonstration would start from")
def simulation_state(db: Session = Depends(get_session)) -> dict:
    return simulation_service.reset_simulation_state(db)


@router.get("/simulation/steps", response_model=list[str], summary="Scenario step keys")
def simulation_steps() -> list[str]:
    return list(simulation_service.STEP_KEYS)
