"""Operational data exchange: real Excel files in and out.

The plant keeps working with spreadsheets; SLCC produces them, reads them back
and shows their content zone by zone without opening Excel.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.schemas.common import UtcDatetime
from app.services import excel_service

router = APIRouter(prefix="/data", tags=["data-exchange"])

XLSX_MEDIA = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

ZONE_FILES = {
    "RECEIVING": "SLCC_Receiving.xlsx",
    "INSPECTION": "SLCC_Inspection.xlsx",
    "QUALITY": "SLCC_Quality.xlsx",
    "WAREHOUSE": "SLCC_Warehouse.xlsx",
    "PRODUCTION": "SLCC_Production.xlsx",
}

ZONE_LABELS = {
    "RECEIVING": ("Reception", "Livraisons et controle des quantites"),
    "INSPECTION": ("Inspection", "Echantillonnages et resultats"),
    "QUALITY": ("Qualite", "Decisions qualite et Red Cage"),
    "WAREHOUSE": ("Warehouse", "Emplacements, stock et mouvements"),
    "PRODUCTION": ("Production", "Demandes des stations"),
}


class SheetInfo(BaseModel):
    name: str
    rows: int


class ZoneInfo(BaseModel):
    zone: str
    label: str
    description: str
    filename: str
    rows: int


class WorkbookStatus(BaseModel):
    """What the Data page shows about the shared workbook."""

    workbook: str
    status: str
    generated_at: UtcDatetime
    sheet_count: int
    row_count: int
    sheets: list[SheetInfo]
    zones: list[ZoneInfo]


class ZoneTable(BaseModel):
    zone: str
    columns: list[str]
    rows: list[list] = Field(default_factory=list)
    total_rows: int
    returned_rows: int
    status_column: str | None = None


@router.get("/status", response_model=WorkbookStatus, summary="Etat du fichier partage")
def workbook_status(db: Session = Depends(get_session)) -> WorkbookStatus:
    summary = excel_service.workbook_summary(db)

    zones = []
    for zone, filename in ZONE_FILES.items():
        label, description = ZONE_LABELS[zone]
        table = excel_service.zone_table(db, zone, limit=1)
        zones.append(
            ZoneInfo(
                zone=zone,
                label=label,
                description=description,
                filename=filename,
                rows=table["total_rows"],
            )
        )

    return WorkbookStatus(
        workbook=summary["workbook"],
        status="SYNCHRONISE",
        generated_at=summary["generated_at"],
        sheet_count=summary["sheet_count"],
        row_count=summary["row_count"],
        sheets=[SheetInfo(**sheet) for sheet in summary["sheets"]],
        zones=zones,
    )


@router.get("/zones/{zone}", response_model=ZoneTable, summary="Donnees d une zone")
def zone_data(
    zone: str,
    limit: int = Query(default=500, le=5000),
    db: Session = Depends(get_session),
) -> ZoneTable:
    """The zone content, so the operator reads it in SLCC rather than in Excel."""
    return ZoneTable.model_validate(excel_service.zone_table(db, zone, limit=limit))


@router.get("/zones/{zone}/export", summary="Telecharger le fichier Excel d une zone")
def zone_export(
    zone: str,
    template: bool = Query(
        default=False,
        description="Renvoyer la feuille SAISIE vide au lieu du fichier de la zone",
    ),
    db: Session = Depends(get_session),
) -> Response:
    """The zone workbook.

    By default it is the file as it sits in the shared folder, SAISIE lines
    included. `template=true` returns the same workbook with an empty entry
    grid, for an operator starting a new batch.
    """
    zone = zone.upper()
    content = excel_service.build_zone_workbook(db, zone, prefill=not template)
    filename = ZONE_FILES.get(zone, f"SLCC_{zone.title()}.xlsx")
    if template:
        filename = filename.replace(".xlsx", "_MODELE.xlsx")
    return Response(
        content=content,
        media_type=XLSX_MEDIA,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/workbook", summary="Telecharger le fichier partage complet")
def workbook_export(db: Session = Depends(get_session)) -> Response:
    content = excel_service.build_global_workbook(db)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return Response(
        content=content,
        media_type=XLSX_MEDIA,
        headers={
            "Content-Disposition": (
                f'attachment; filename="SLCC_Logistics_Flow_{stamp}.xlsx"'
            )
        },
    )
