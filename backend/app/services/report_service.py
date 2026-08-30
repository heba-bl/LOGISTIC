"""Reports: a period, a subject, and an export.

Every report is a small, flat table plus a handful of headline figures. The point
is that the logistics manager reads a conclusion, not 500 spreadsheet lines.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ValidationError
from app.core.timeutils import to_local
from app.models.enums import InspectionResult, LotStatus, MovementType
from app.models.flow import Inspection, Reception
from app.models.production import ProductionRequest
from app.models.warehouse import Stock, StockMovement, WarehouseLocation
from app.repositories import LotRepository, ProductionRepository
from app.services import dashboard_service, warehouse_service

PERIODS = ("today", "week", "month", "year", "custom")


@dataclass
class Report:
    key: str
    title: str
    period_label: str
    columns: list[str]
    rows: list[list[Any]]
    summary: list[dict] = field(default_factory=list)
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def resolve_period(
    period: str, date_from: date | None = None, date_to: date | None = None
) -> tuple[datetime, datetime, str]:
    """Turn a period name into an inclusive UTC window plus a readable label."""
    if period not in PERIODS:
        raise ValidationError(f"Periode inconnue: {period}")

    today = to_local(datetime.now(timezone.utc)).date()

    if period == "custom":
        if not date_from or not date_to:
            raise ValidationError("Une periode personnalisee exige une date de debut et de fin")
        if date_to < date_from:
            raise ValidationError("La date de fin precede la date de debut")
        start, end = date_from, date_to
        label = f"du {start:%d/%m/%Y} au {end:%d/%m/%Y}"
    elif period == "today":
        start = end = today
        label = f"le {today:%d/%m/%Y}"
    elif period == "week":
        start = today - timedelta(days=today.weekday())
        end = today
        label = f"semaine du {start:%d/%m/%Y}"
    elif period == "month":
        start = today.replace(day=1)
        end = today
        label = f"{start:%m/%Y}"
    else:  # year
        start = today.replace(month=1, day=1)
        end = today
        label = f"annee {start:%Y}"

    # Local day bounds converted to UTC, so a report on "today" means the
    # operator's today, not UTC's.
    begin = datetime.combine(start, time.min).astimezone().astimezone(timezone.utc)
    finish = datetime.combine(end, time.max).astimezone().astimezone(timezone.utc)
    return begin, finish, label


def _fmt(value: datetime | None) -> str:
    return to_local(value).strftime("%d/%m/%Y %H:%M") if value else ""


# --------------------------------------------------------------------- reports
def report_receptions(db: Session, start: datetime, end: datetime) -> tuple[list, list, list]:
    rows, accepted, tolerance, mismatch, total_qty = [], 0, 0, 0, 0
    query = (
        select(Reception)
        .where(Reception.received_at >= start, Reception.received_at <= end)
        .order_by(Reception.id.desc())
    )
    for reception in db.execute(query).scalars():
        lot = reception.lot
        total_qty += reception.quantity_received
        if reception.status.value == "ACCEPTED":
            accepted += 1
        elif reception.status.value == "ACCEPTED_WITH_TOLERANCE":
            tolerance += 1
        else:
            mismatch += 1
        rows.append([
            _fmt(reception.received_at), reception.reference, lot.lot_number,
            lot.part.reference, lot.supplier.name, reception.quantity_expected,
            reception.quantity_received, reception.quantity_gap,
            reception.received_by.employee_number if reception.received_by else "",
            reception.status.value,
        ])
    columns = ["DATE", "RECEPTION", "LOT", "REFERENCE", "FOURNISSEUR",
               "ATTENDU", "RECU", "ECART", "MATRICULE", "STATUT"]
    summary = [
        {"label": "Receptions", "value": len(rows), "severity": "INFO"},
        {"label": "Quantite recue", "value": total_qty, "unit": "PCS", "severity": "OK"},
        {"label": "Conformes", "value": accepted, "severity": "OK"},
        {"label": "Dans la tolerance", "value": tolerance, "severity": "WARNING" if tolerance else "OK"},
        {"label": "Hors tolerance", "value": mismatch, "severity": "CRITICAL" if mismatch else "OK"},
    ]
    return columns, rows, summary


def report_quality(db: Session, start: datetime, end: datetime) -> tuple[list, list, list]:
    rows, conform, non_conform, defects = [], 0, 0, 0
    query = (
        select(Inspection)
        .where(Inspection.inspected_at >= start, Inspection.inspected_at <= end)
        .order_by(Inspection.id.desc())
    )
    for inspection in db.execute(query).scalars():
        lot = inspection.lot
        defects += inspection.defects_found
        if inspection.result is InspectionResult.CONFORM:
            conform += 1
        else:
            non_conform += 1
        rows.append([
            _fmt(inspection.inspected_at), inspection.reference, lot.lot_number,
            lot.part.reference, lot.supplier.name, inspection.sample_size,
            inspection.defects_found, inspection.defect_rate_percent,
            inspection.inspector.employee_number if inspection.inspector else "",
            inspection.result.value,
        ])
    total = conform + non_conform
    rate = round(conform / total * 100, 1) if total else 100.0
    columns = ["DATE", "INSPECTION", "LOT", "REFERENCE", "FOURNISSEUR",
               "ECHANTILLON", "DEFAUTS", "TAUX_%", "MATRICULE", "RESULTAT"]
    summary = [
        {"label": "Inspections", "value": total, "severity": "INFO"},
        {"label": "Taux de conformite", "value": rate, "unit": "%",
         "severity": "OK" if rate >= 95 else "WARNING"},
        {"label": "Non conformes", "value": non_conform,
         "severity": "CRITICAL" if non_conform else "OK"},
        {"label": "Defauts releves", "value": defects, "severity": "INFO"},
    ]
    return columns, rows, summary


def report_red_cage(db: Session, start: datetime, end: datetime) -> tuple[list, list, list]:
    rows, blocked_qty = [], 0
    for lot in LotRepository(db).in_stage([LotStatus.RED_CAGE, LotStatus.REJECTED]):
        blocked_qty += lot.quantity_received
        rows.append([
            _fmt(lot.received_at), lot.lot_number, lot.part.reference,
            lot.supplier.name, lot.quantity_received,
            lot.blocked_reason or "", lot.status.value,
        ])
    columns = ["DATE_RECEPTION", "LOT", "REFERENCE", "FOURNISSEUR",
               "QUANTITE", "MOTIF", "STATUT"]
    summary = [
        {"label": "Lots bloques", "value": len(rows),
         "severity": "CRITICAL" if rows else "OK"},
        {"label": "Quantite immobilisee", "value": blocked_qty, "unit": "PCS",
         "severity": "WARNING" if blocked_qty else "OK"},
    ]
    return columns, rows, summary


def report_stock(db: Session, start: datetime, end: datetime) -> tuple[list, list, list]:
    rows, total, below = [], 0, 0
    production = ProductionRepository(db)
    for stock in db.execute(select(Stock)).scalars():
        part = stock.part
        total += stock.quantity_available
        demand = production.demand_for_part(part.id)
        under = part.safety_stock and stock.quantity_available < part.safety_stock
        if under:
            below += 1
        cover = (
            round(stock.quantity_available / part.average_daily_consumption, 1)
            if part.average_daily_consumption else None
        )
        rows.append([
            part.reference, part.designation,
            part.category.name if part.category else "",
            stock.quantity_available, stock.quantity_reserved, part.safety_stock,
            demand, cover if cover is not None else "",
            "SOUS SEUIL" if under else "OK",
        ])
    columns = ["REFERENCE", "DESIGNATION", "CATEGORIE", "DISPONIBLE",
               "RESERVE", "STOCK_SECURITE", "DEMANDE", "COUVERTURE_J", "STATUT"]
    summary = [
        {"label": "Stock total", "value": total, "unit": "PCS", "severity": "OK"},
        {"label": "References", "value": len(rows), "severity": "INFO"},
        {"label": "Sous le seuil", "value": below,
         "severity": "CRITICAL" if below else "OK"},
    ]
    return columns, rows, summary


def report_warehouse(db: Session, start: datetime, end: datetime) -> tuple[list, list, list]:
    overview = warehouse_service.occupancy_overview(db)
    rows = []
    for location in db.execute(
        select(WarehouseLocation).order_by(WarehouseLocation.zone, WarehouseLocation.position)
    ).scalars():
        rows.append([
            location.code, location.zone, location.capacity, location.occupied,
            location.free_capacity, location.occupancy_percent,
            warehouse_service.location_severity(location),
        ])
    columns = ["EMPLACEMENT", "ZONE", "CAPACITE", "OCCUPE", "LIBRE",
               "OCCUPATION_%", "STATUT"]
    summary = [
        {"label": "Occupation globale", "value": overview["occupancy_percent"],
         "unit": "%", "severity": "WARNING" if overview["nearly_full"] else "OK"},
        {"label": "Emplacements satures", "value": len(overview["saturated"]),
         "severity": "CRITICAL" if overview["saturated"] else "OK"},
        {"label": "Presque pleins", "value": len(overview["nearly_full"]),
         "severity": "WARNING" if overview["nearly_full"] else "OK"},
    ]
    return columns, rows, summary


def report_production(db: Session, start: datetime, end: datetime) -> tuple[list, list, list]:
    rows, requested, issued, open_count = [], 0, 0, 0
    query = (
        select(ProductionRequest)
        .where(ProductionRequest.created_on >= start, ProductionRequest.created_on <= end)
        .order_by(ProductionRequest.id.desc())
    )
    for request in db.execute(query).scalars():
        requested += request.quantity_requested
        issued += request.quantity_issued
        if request.is_open:
            open_count += 1
        rows.append([
            _fmt(request.created_on), request.reference, request.station.code,
            request.part.reference, request.quantity_requested, request.quantity_issued,
            request.priority,
            request.requested_by.employee_number if request.requested_by else "",
            request.status.value,
        ])
    rate = round(issued / requested * 100, 1) if requested else 0.0
    columns = ["DATE", "DEMANDE", "STATION", "REFERENCE", "DEMANDE_QTE",
               "SORTIE_QTE", "PRIORITE", "MATRICULE", "STATUT"]
    summary = [
        {"label": "Demandes", "value": len(rows), "severity": "INFO"},
        {"label": "Quantite demandee", "value": requested, "unit": "PCS", "severity": "INFO"},
        {"label": "Quantite sortie", "value": issued, "unit": "PCS", "severity": "OK"},
        {"label": "Taux de service", "value": rate, "unit": "%",
         "severity": "OK" if rate >= 90 else "WARNING"},
        {"label": "En cours", "value": open_count, "severity": "INFO"},
    ]
    return columns, rows, summary


def report_consumption(db: Session, start: datetime, end: datetime) -> tuple[list, list, list]:
    query = (
        select(StockMovement)
        .where(
            StockMovement.movement_type == MovementType.OUT,
            StockMovement.occurred_at >= start,
            StockMovement.occurred_at <= end,
        )
        .order_by(StockMovement.id.desc())
    )
    rows, total = [], 0
    per_part: dict[str, int] = {}
    for movement in db.execute(query).scalars():
        total += movement.quantity
        reference = movement.part.reference
        per_part[reference] = per_part.get(reference, 0) + movement.quantity
        rows.append([
            _fmt(movement.occurred_at), movement.reference, reference,
            movement.quantity, movement.station.code if movement.station else "",
            movement.actor_name, movement.reason or "",
        ])
    top = max(per_part.items(), key=lambda item: item[1])[0] if per_part else "-"
    columns = ["DATE", "MOUVEMENT", "REFERENCE", "QUANTITE", "STATION",
               "OPERATEUR", "MOTIF"]
    summary = [
        {"label": "Sorties", "value": len(rows), "severity": "INFO"},
        {"label": "Quantite consommee", "value": total, "unit": "PCS", "severity": "INFO"},
        {"label": "References concernees", "value": len(per_part), "severity": "INFO"},
        {"label": "Plus consommee", "value": top, "severity": "INFO"},
    ]
    return columns, rows, summary


def report_alerts(db: Session, start: datetime, end: datetime) -> tuple[list, list, list]:
    alerts = dashboard_service.build_alerts(db)
    rows = [
        [
            _fmt(alert["timestamp"]), alert["severity"], alert["title"],
            alert["message"], alert["source"],
        ]
        for alert in alerts
    ]
    critical = sum(1 for alert in alerts if alert["severity"] == "CRITICAL")
    columns = ["DATE", "NIVEAU", "TITRE", "MESSAGE", "SOURCE"]
    summary = [
        {"label": "Alertes actives", "value": len(rows),
         "severity": "CRITICAL" if critical else "OK"},
        {"label": "Critiques", "value": critical,
         "severity": "CRITICAL" if critical else "OK"},
    ]
    return columns, rows, summary


def report_kpi(db: Session, start: datetime, end: datetime) -> tuple[list, list, list]:
    kpis = dashboard_service.build_kpis(db)
    rows = [
        [kpi["label"], kpi["value"], kpi["unit"] or "", kpi["hint"], kpi["severity"]]
        for kpi in kpis
    ]
    columns = ["INDICATEUR", "VALEUR", "UNITE", "DETAIL", "NIVEAU"]
    summary = [
        {"label": kpi["label"], "value": kpi["value"], "unit": kpi["unit"] or None,
         "severity": kpi["severity"]}
        for kpi in kpis
    ]
    return columns, rows, summary


BUILDERS: dict[str, tuple[str, Callable]] = {
    "receptions": ("Rapport des receptions", report_receptions),
    "quality": ("Rapport qualite", report_quality),
    "red_cage": ("Rapport Red Cage", report_red_cage),
    "stock": ("Rapport de stock", report_stock),
    "warehouse": ("Rapport entrepot", report_warehouse),
    "production": ("Rapport de production", report_production),
    "consumption": ("Rapport de consommation", report_consumption),
    "alerts": ("Rapport des alertes", report_alerts),
    "kpi": ("Indicateurs cles", report_kpi),
}


def build_report(
    db: Session, kind: str, period: str, date_from: date | None, date_to: date | None
) -> Report:
    if kind not in BUILDERS:
        raise ValidationError(f"Rapport inconnu: {kind}")
    title, builder = BUILDERS[kind]
    start, end, label = resolve_period(period, date_from, date_to)
    columns, rows, summary = builder(db, start, end)
    return Report(
        key=kind, title=title, period_label=label,
        columns=columns, rows=rows, summary=summary,
    )


# --------------------------------------------------------------------- exports
def report_to_xlsx(report: Report) -> bytes:
    from openpyxl import Workbook

    from app.services.excel_service import SYNTHETIC_NOTICE, write_table

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = report.key.upper()[:31]
    write_table(
        sheet,
        title=f"{report.title} - {report.period_label}",
        subtitle=SYNTHETIC_NOTICE,
        headers=report.columns,
        rows=report.rows,
        table_name=f"T_{report.key.upper()}",
        status_column="STATUT" if "STATUT" in report.columns else (
            "RESULTAT" if "RESULTAT" in report.columns else None
        ),
    )
    buffer = io.BytesIO()
    workbook.save(buffer)
    workbook.close()
    return buffer.getvalue()


def report_to_pdf(report: Report) -> bytes:
    """A print-ready PDF: headline figures then the detail table."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer, pagesize=landscape(A4),
        leftMargin=14 * mm, rightMargin=14 * mm,
        topMargin=14 * mm, bottomMargin=14 * mm,
        title=report.title,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "SlccTitle", parent=styles["Title"], fontSize=16, alignment=0, spaceAfter=2,
        textColor=colors.HexColor("#1F2937"),
    )
    sub_style = ParagraphStyle(
        "SlccSub", parent=styles["Normal"], fontSize=8.5,
        textColor=colors.HexColor("#6B7280"), spaceAfter=8,
    )
    cell_style = ParagraphStyle("SlccCell", parent=styles["Normal"], fontSize=7, leading=9)

    story = [
        Paragraph(report.title, title_style),
        Paragraph(
            f"Periode : {report.period_label} &nbsp;|&nbsp; "
            f"Genere le {to_local(report.generated_at):%d/%m/%Y %H:%M} &nbsp;|&nbsp; "
            "Jeu de donnees synthetique - demonstration SLCC",
            sub_style,
        ),
    ]

    if report.summary:
        data = [[item["label"] for item in report.summary],
                [f"{item['value']}{(' ' + item['unit']) if item.get('unit') else ''}"
                 for item in report.summary]]
        summary_table = Table(data, hAlign="LEFT")
        summary_table.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#6B7280")),
            ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 1), (-1, 1), 12),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LINEBELOW", (0, 1), (-1, 1), 0.6, colors.HexColor("#D1D5DB")),
        ]))
        story += [summary_table, Spacer(1, 10)]

    if report.rows:
        head = [Paragraph(f"<b>{column}</b>", cell_style) for column in report.columns]
        body = [
            [Paragraph(str(value if value is not None else ""), cell_style) for value in row]
            for row in report.rows[:400]
        ]
        table = Table([head] + body, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#374151")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D1D5DB")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.white, colors.HexColor("#F9FAFB")]),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(table)
        if len(report.rows) > 400:
            story += [Spacer(1, 6), Paragraph(
                f"{len(report.rows) - 400} lignes supplementaires disponibles "
                "dans l export Excel.", sub_style)]
    else:
        story.append(Paragraph("Aucune donnee sur la periode selectionnee.", sub_style))

    document.build(story)
    return buffer.getvalue()
