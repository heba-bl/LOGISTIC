"""Write `SLCC_Logistics_Operations.xlsm` into the shared folder.

The ARTICLES sheet carries the stock as the database holds it at the moment of
writing, stamped with that moment. Re-run this after a synchronisation to
refresh the picture:

    python scripts/generate_operations_xlsm.py

The database stays the only source of truth for the stock; this file is a dated
photograph of it, and says so on the sheet.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal  # noqa: E402
from app.services import excel_operations  # noqa: E402

TARGET = (
    Path(__file__).resolve().parents[2]
    / "shared-folder"
    / "00_FICHIER_PARTAGE"
    / excel_operations.WORKBOOK_NAME
)


def main() -> int:
    session = SessionLocal()
    try:
        content = excel_operations.build_workbook(db=session)
    finally:
        session.close()

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_bytes(content)

    summary = excel_operations.workbook_summary(content)
    print(f"{TARGET}")
    print(f"  {len(content):,} octets, {summary['sheet_count']} feuilles")
    for sheet in summary["sheets"]:
        print(f"    {sheet['name']:20} {sheet['rows']:>6}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
