"""Reports: period filters, headline figures, Excel and PDF export."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.schemas.common import UtcDatetime
from app.services import report_service

router = APIRouter(prefix="/reports", tags=["reports"])

XLSX_MEDIA = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

REPORT_LABELS = {
    "receptions": ("Receptions", "Livraisons et ecarts de quantite"),
    "quality": ("Qualite", "Inspections, conformite et defauts"),
    "red_cage": ("Red Cage", "Lots bloques et quantites immobilisees"),
    "stock": ("Stock", "Disponible, reserve et couverture"),
    "warehouse": ("Entrepot", "Occupation des emplacements"),
    "production": ("Production", "Demandes et taux de service"),
    "consumption": ("Consommation", "Sorties de stock par reference"),
    "alerts": ("Alertes", "Signaux actifs du systeme"),
    "kpi": ("Indicateurs", "KPI de supervision"),
}


class ReportKind(BaseModel):
    key: str
    label: str
    description: str


class SummaryItem(BaseModel):
    label: str
    value: float | str
    unit: str | None = None
    severity: str = "INFO"


class ReportOut(BaseModel):
    key: str
    title: str
    period: str
    period_label: str
    generated_at: UtcDatetime
    columns: list[str]
    rows: list[list] = Field(default_factory=list)
    summary: list[SummaryItem] = Field(default_factory=list)
    row_count: int


@router.get("/kinds", response_model=list[ReportKind], summary="Rapports disponibles")
def report_kinds() -> list[ReportKind]:
    return [
        ReportKind(key=key, label=label, description=description)
        for key, (label, description) in REPORT_LABELS.items()
    ]


@router.get("/{kind}", response_model=ReportOut, summary="Generer un rapport")
def get_report(
    kind: str,
    period: str = Query(default="month"),
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(default=500, le=5000),
    db: Session = Depends(get_session),
) -> ReportOut:
    report = report_service.build_report(db, kind, period, date_from, date_to)
    return ReportOut(
        key=report.key,
        title=report.title,
        period=period,
        period_label=report.period_label,
        generated_at=report.generated_at,
        columns=report.columns,
        rows=report.rows[:limit],
        summary=[SummaryItem(**item) for item in report.summary],
        row_count=len(report.rows),
    )


@router.get("/{kind}/export.xlsx", summary="Exporter un rapport en Excel")
def export_xlsx(
    kind: str,
    period: str = Query(default="month"),
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_session),
) -> Response:
    report = report_service.build_report(db, kind, period, date_from, date_to)
    content = report_service.report_to_xlsx(report)
    return Response(
        content=content,
        media_type=XLSX_MEDIA,
        headers={
            "Content-Disposition": f'attachment; filename="SLCC_rapport_{kind}_{period}.xlsx"'
        },
    )


@router.get("/{kind}/export.pdf", summary="Exporter un rapport en PDF")
def export_pdf(
    kind: str,
    period: str = Query(default="month"),
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_session),
) -> Response:
    report = report_service.build_report(db, kind, period, date_from, date_to)
    content = report_service.report_to_pdf(report)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="SLCC_rapport_{kind}_{period}.pdf"'
        },
    )
