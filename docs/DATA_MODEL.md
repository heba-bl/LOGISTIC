# Data model

21 tables, defined in `backend/app/models/` and created by Alembic migrations
`0002_business_model` and `0003_maker_checker`. Enums are persisted as `VARCHAR` with a `CHECK` constraint
so the schema is identical on PostgreSQL and on the SQLite development fallback.

---

## Entities

### Organisation
| Table | Purpose |
|-------|---------|
| `roles` | the eight simulated roles, with `can_validate` |
| `users` | operators: **matricule**, role, service, active flag |

### Catalogue
| Table | Purpose |
|-------|---------|
| `suppliers` | supplier, country, contractual lead time |
| `categories` | part families |
| `parts` | reference, size class, tolerance override, safety stock, daily consumption |

### Inbound flow
| Table | Purpose |
|-------|---------|
| `lots` | a batch of one reference from one supplier; carries the status |
| `receptions` | the quantity check (expected, received, gap, tolerance applied) |
| `inspections` | sample size, defects, threshold, result |
| `quality_validations` | decision + mandatory justification |

### Warehouse and stock
| Table | Purpose |
|-------|---------|
| `warehouses` | site |
| `warehouse_locations` | address, zone, capacity, occupancy, thresholds |
| `part_locations` | addressing: one PRIMARY per reference, N SECONDARY |
| `stock` | available and reserved quantity per reference (`CHECK >= 0`) |
| `stock_movements` | immutable ledger, with quantity before/after |

### Production
| Table | Purpose |
|-------|---------|
| `production_stations` | stations and their line |
| `production_requests` | request, workflow status, priority, issued quantity |

### Import and validation
| Table | Purpose |
|-------|---------|
| `data_imports` | one uploaded spreadsheet: maker, checker, decision, file hash |
| `import_rows` | one line of the file: payload, status, error, produced reference |

### Cross-cutting
| Table | Purpose |
|-------|---------|
| `audit_logs` | append-only trace: actor **and** maker/checker/decision/source file |
| `ai_recommendations` | analysis output; `rationale` is NOT NULL |
| `system_settings` | tunable business thresholds |

---

## Relations

```
Supplier ─┬─< Lot >─┬─ Part ─< Stock >─< StockMovement
          │         ├─── Reception (1:1)
          │         ├─── Inspection (1:N)
          │         ├─── QualityValidation (1:N)
          │         └─── WarehouseLocation (where stored)

Part ─< PartLocation >─ WarehouseLocation      (primary + secondary addressing)
Warehouse ─< WarehouseLocation

ProductionStation ─< ProductionRequest >─ Part
ProductionRequest ─< StockMovement

Every significant event ─> AuditLog
```

---

## State machines

### Lot

```
PENDING_INSPECTION ──► INSPECTION_IN_PROGRESS ──► QUALITY_PENDING ──► APPROVED ──► STORED ──► CONSUMED
        │                        │                      │                │
        └──────────────► RED_CAGE ◄────────────────────┘                │
                            │                                            │
                            ├──► APPROVED  (released with a derogation)  │
                            └──► REJECTED  (scrapped)                    │
```

`STORED` and `CONSUMED` extend the six states of the specification: they are what
distinguishes "quality approved" from "physically in stock", which is exactly the
distinction the stock rule depends on.

### Production request

```
DRAFT ──► SUBMITTED ──► APPROVED ──► PREPARING ──► READY ──► ISSUED
              │              │            │           │
              ├──► REJECTED  └────────────┴───────────┴──► CANCELLED
```

### Reception check

`ACCEPTED` · `ACCEPTED_WITH_TOLERANCE` · `QUANTITY_MISMATCH`

### Data import (Maker-Checker)

```
IMPORTED ──► PENDING_REVIEW ──► APPROVED   (rows applied by the services)
                             └► REJECTED   (nothing applied, comment mandatory)
```

Row status: `PENDING` · `INVALID` (refused by the parser) · `APPLIED` ·
`REJECTED` (batch refused) · `FAILED` (approved but the business rule refused it).

---

## Design decisions

- **`quantity_before` / `quantity_after` on every movement** — the ledger can be
  replayed and audited without recomputing from scratch.
- **`Stock.quantity_reserved`** — an approved request commits stock without
  reducing the available quantity, so the stock rule stays intact while the
  screens can still show what is genuinely free.
- **`Lot.quantity_available`** — what remains of a lot in stock, so FIFO
  consumption and per-address release stay consistent with the global figure.
- **`AIRecommendation.rationale` NOT NULL** — the specification forbids an
  unexplained recommendation; the schema enforces it.
- **`AuditLog` never updated or deleted** — it is the traceability record.
- **Naming convention on `Base.metadata`** — Alembic autogenerate produces stable
  constraint names across engines.

---

## Migrations

| Revision | Content |
|----------|---------|
| `0001_baseline` | empty baseline (Phase 1) |
| `0002_business_model` | the 19 business tables |
| `0003_maker_checker` | matricule, service, `can_validate`, imports, audit identity |

`0003` adds two `NOT NULL` columns to populated tables, so it adds them nullable,
backfills, then applies the constraint — it runs on an existing database.

```bash
cd backend
alembic upgrade head
alembic revision --autogenerate -m "your change"
```
