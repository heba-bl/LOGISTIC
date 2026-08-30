"""Write the operational workbooks into the shared folder.

This reproduces what the plant does today: a network folder that every zone can
reach, one sub-folder per zone with the file that zone fills in, and one shared
workbook that consolidates everything for the logistics manager.

    shared-folder/
        LISEZ-MOI.md
        00_FICHIER_PARTAGE/SLCC_Logistics_Flow.xlsx   (12 sheets, all zones)
        01_RECEPTION/SLCC_Receiving.xlsx
        02_INSPECTION/SLCC_Inspection.xlsx
        03_QUALITE/SLCC_Quality.xlsx
        04_ENTREPOT/SLCC_Warehouse.xlsx
        05_PRODUCTION/SLCC_Production.xlsx

The zone files ship with their SAISIE sheet already filled, because that is what
an operator actually hands over. Filling a sheet still moves nothing: the file
has to be imported into SLCC and validated by a different, habilitated person.

Run from the backend/ directory:

    python scripts/generate_excel.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.timeutils import to_local  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.services import excel_service  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "shared-folder"

#: zone key -> (sub-folder, file name, what the zone does with it)
ZONE_FILES = {
    "RECEIVING": (
        "01_RECEPTION",
        "SLCC_Receiving.xlsx",
        "Saisie des livraisons fournisseur et historique des receptions",
    ),
    "INSPECTION": (
        "02_INSPECTION",
        "SLCC_Inspection.xlsx",
        "Saisie des controles par echantillonnage et historique des inspections",
    ),
    "QUALITE": (
        "03_QUALITE",
        "SLCC_Quality.xlsx",
        "Decisions qualite et lots bloques en Red Cage",
    ),
    "ENTREPOT": (
        "04_ENTREPOT",
        "SLCC_Warehouse.xlsx",
        "Emplacements, stock disponible et mouvements",
    ),
    "PRODUCTION": (
        "05_PRODUCTION",
        "SLCC_Production.xlsx",
        "Saisie des demandes de pieces et suivi des sorties",
    ),
}

#: The workbook builder still speaks the internal zone names.
BUILDER_ZONE = {
    "RECEIVING": "RECEIVING",
    "INSPECTION": "INSPECTION",
    "QUALITE": "QUALITY",
    "ENTREPOT": "WAREHOUSE",
    "PRODUCTION": "PRODUCTION",
}

GLOBAL_FOLDER = "00_FICHIER_PARTAGE"
GLOBAL_FILE = "SLCC_Logistics_Flow.xlsx"


def readme(summary: dict, generated_at: datetime) -> str:
    stamp = to_local(generated_at).strftime("%d/%m/%Y %H:%M")
    lines = [
        "# Dossier partage SLCC",
        "",
        "**Jeu de donnees synthetique - demonstration.** Ces fichiers sont produits "
        "a partir de la base de demonstration SLCC. Les identites, les fournisseurs "
        "et les references sont fictifs et n'appartiennent a aucune entreprise reelle.",
        "",
        f"Genere le {stamp} par `python scripts/generate_excel.py`.",
        "",
        "## Organisation",
        "",
        "Chaque zone dispose de son sous-dossier et de son fichier. Le fichier "
        "partage consolide les douze feuilles de l'ensemble du flux.",
        "",
        "| Dossier | Fichier | Contenu |",
        "|---------|---------|---------|",
        f"| `{GLOBAL_FOLDER}/` | `{GLOBAL_FILE}` | Fichier partage, 12 feuilles, toutes zones |",
    ]
    for folder, filename, description in ZONE_FILES.values():
        lines.append(f"| `{folder}/` | `{filename}` | {description} |")

    lines += [
        "",
        "## Comment travailler avec ces fichiers",
        "",
        "1. L'operateur ouvre le fichier de sa zone et remplit la feuille `SAISIE`, "
        "une ligne par enregistrement. Il ne renomme aucun en-tete.",
        "2. Il enregistre le fichier dans son sous-dossier.",
        "3. Dans SLCC, page **Donnees operationnelles**, le fichier est importe. "
        "Chaque ligne est controlee et le lot reste `EN ATTENTE DE VALIDATION`.",
        "4. Un responsable habilite de la zone - obligatoirement une autre personne "
        "que celle qui a saisi - approuve ou rejette l'import dans SLCC.",
        "5. Les enregistrements ne sont crees qu'apres cette validation.",
        "",
        "**Le mot de passe personnel du responsable n'est jamais saisi dans Excel.** "
        "La validation se fait uniquement dans SLCC.",
        "",
        "## Regle du stock",
        "",
        "Remplir un fichier Excel ne modifie jamais le stock. Le stock ne bouge que sur:",
        "",
        "- **STOCK +** : reception -> inspection -> validation qualite -> "
        "**confirmation de stockage**",
        "- **STOCK -** : demande -> validation -> preparation -> **sortie confirmee**",
        "",
        "Chaque mouvement produit un `StockMovement` et une entree d'audit "
        "nominative. Le stock ne peut jamais devenir negatif.",
        "",
        "## Feuilles du fichier partage",
        "",
        "| Feuille | Lignes |",
        "|---------|--------|",
    ]
    for sheet in summary["sheets"]:
        lines.append(f"| `{sheet['name']}` | {sheet['rows']:,} |".replace(",", " "))
    lines.append("")
    lines.append(
        f"Total: {summary['sheet_count']} feuilles, "
        f"{summary['row_count']:,} lignes de donnees.".replace(",", " ")
    )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    db = SessionLocal()

    try:
        print(f"Dossier partage: {OUTPUT_DIR}")
        total_bytes = 0

        for zone, (folder, filename, _description) in ZONE_FILES.items():
            target_dir = OUTPUT_DIR / folder
            target_dir.mkdir(parents=True, exist_ok=True)
            content = excel_service.build_zone_workbook(
                db, BUILDER_ZONE[zone], prefill=True
            )
            (target_dir / filename).write_bytes(content)
            total_bytes += len(content)
            print(f"  {folder}/{filename:26} {len(content):>9,} octets")

        shared_dir = OUTPUT_DIR / GLOBAL_FOLDER
        shared_dir.mkdir(parents=True, exist_ok=True)
        content = excel_service.build_global_workbook(db)
        (shared_dir / GLOBAL_FILE).write_bytes(content)
        total_bytes += len(content)
        print(f"  {GLOBAL_FOLDER}/{GLOBAL_FILE:22} {len(content):>9,} octets")

        summary = excel_service.workbook_summary(db)
        print(
            f"\n  {summary['sheet_count']} feuilles, "
            f"{summary['row_count']:,} lignes de donnees dans le fichier partage"
        )
        for sheet in summary["sheets"]:
            print(f"    {sheet['name']:18} {sheet['rows']:>6,}")

        generated_at = datetime.now(timezone.utc)
        (OUTPUT_DIR / "LISEZ-MOI.md").write_text(
            readme(summary, generated_at), encoding="utf-8"
        )
        print(f"\n  LISEZ-MOI.md ecrit ({total_bytes:,} octets au total)")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
