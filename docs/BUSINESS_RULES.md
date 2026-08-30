# Business rules

Every rule below is enforced **server-side**. The frontend never decides that an
operation is valid: it calls the API, the service checks the rule, and the UI
renders whatever the backend decided.

---

## 1. The stock rule (non-negotiable)

```
IN    Reception → Inspection → Quality validation → Storage confirmed → STOCK +
OUT   Request   → Validation → Preparation        → Issue confirmed   → STOCK -
```

| Operation | Touches stock? | Where |
|-----------|----------------|-------|
| Create a reception | **No** | `reception_service.create_reception` |
| Record an inspection | **No** | `inspection_service.record_inspection` |
| Approve a lot | **No** — only unlocks storage | `quality_service.approve` |
| **Confirm storage** | **YES, +** | `warehouse_service.confirm_storage` |
| Create a request | **No** | `production_service.create_request` |
| Approve a request | **No** — reserves only | `production_service.approve` |
| Prepare / mark ready | **No** | `production_service` |
| **Confirm the issue** | **YES, −** | `production_service.issue` |

Guarantees:

1. `stock_service` is the only module that writes `Stock.quantity_available`.
2. Every change writes a `StockMovement` **and** an `AuditLog` in the same
   transaction as the workflow transition that justified it.
3. Each movement records `quantity_before` and `quantity_after`, so the ledger is
   self-checking (tested in `test_movement_ledger_is_self_consistent`).
4. A decrement below zero raises `InsufficientStockError`; a `CHECK` constraint on
   the table is the second line of defence.
5. Storage is refused unless the lot is `APPROVED`, the quantities match the
   approved quantity, and every target address has room.

---

## 2. Reception tolerance

Resolved by `reception_service.resolve_tolerance`, in this order:

1. `Part.reception_tolerance_percent` — a per-part override.
2. Otherwise the setting matching the part class:
   - `reception.tolerance_percent_small` (default **5%**)
   - `reception.tolerance_percent_large` (default **0%** — exact quantity)

| Outcome | Condition | Lot status |
|---------|-----------|------------|
| `ACCEPTED` | received = expected | `PENDING_INSPECTION` |
| `ACCEPTED_WITH_TOLERANCE` | \|gap\| ≤ expected × tolerance | `PENDING_INSPECTION` |
| `QUANTITY_MISMATCH` | beyond tolerance | `RED_CAGE` with the reason recorded |

The percentage appears **once** in the settings table. `GET /api/receptions/tolerance-preview`
returns the rule, its source and the accepted window so the operator sees it before
confirming.

---

## 3. Sampling and inspection

```
sample = min(quantity_received, max(inspection.sample_minimum,
                                    ceil(quantity_received × inspection.sample_percent / 100)))
```

The floor is applied first and then capped by the lot, so a 3-unit lot can never
produce a 5-unit sample.

| Defect rate on the sample | Result | Lot goes to |
|---------------------------|--------|-------------|
| ≤ `inspection.defect_threshold_percent` (default 2%) | `CONFORM` | `QUALITY_PENDING` |
| > threshold | `NON_CONFORM` | `RED_CAGE` |

Rejected inputs: sample ≤ 0, sample > lot, defects < 0, defects > sample.

---

## 4. Quality and the Red Cage

The Red Cage is the quarantine where a lot waits for a human decision. A lot
arrives there from a non-conform inspection **or** an out-of-tolerance reception.

| Action | From | To | Requires |
|--------|------|----|----------|
| Approve | `QUALITY_PENDING`, `RED_CAGE` | `APPROVED` | justification, quantity ≤ received |
| Reject | `QUALITY_PENDING`, `RED_CAGE` | `REJECTED` | justification |
| Quarantine | any non-stored state | `RED_CAGE` | justification |
| Scrap | `RED_CAGE` | `REJECTED` | justification |

A decision is **never** recorded without a justification, and releasing a lot from
the Red Cage is audited as `RED_CAGE_RELEASED` rather than a plain approval.

---

## 5. Warehouse addressing

- Every reference has one **primary** address and may have **secondary** addresses.
- `warehouse_service.suggest_allocations` fills the primary address first, then the
  secondaries, then spills over onto the emptiest free address.
- A lot bigger than its primary address is stored across several addresses; each
  allocation produces its own movement.
- Capacity is validated for **every** target before anything is mutated.
- On issue, shelf space is released from the addresses in the order they were
  filled, so a split lot frees the right shelves.

Occupancy thresholds (`warehouse.warning_occupancy_percent`,
`warehouse.critical_occupancy_percent`) drive the map colours and the saturation
alerts.

---

## 6. Production workflow

```
DRAFT → SUBMITTED → APPROVED → PREPARING → READY → ISSUED
             ↘ REJECTED          ↘ CANCELLED (from any open state)
```

Transitions are declared in `production_service.TRANSITIONS`; anything else raises
`WorkflowError`. Notably a `SUBMITTED` request cannot be issued directly — the
preparation steps cannot be skipped.

Approving reserves the quantity (`Stock.quantity_reserved`) without touching the
available quantity; cancelling an approved request releases the reservation.

---

## 7. Operator identification

An operator is **never anonymous**. Every user carries:

- a unique **employee number** (matricule) — `OP-1042`, `QL-1045`, `WH-008`, `ST-012`;
- a **role**;
- a **service / zone**;
- an **active / inactive** status.

That identity is attached to every action: `AuditLog` stores `actor_reference`
and `actor_role` alongside the name, so the trail names a person, not a label.

| Matricule | Role | Service | May validate |
|-----------|------|---------|--------------|
| OP-1042 | Receptionist | Reception | no |
| RM-004 | Reception Manager | Reception | **yes** |
| QL-1045 | Quality Inspector | Quality | no |
| QM-002 | Quality Manager | Quality | **yes** |
| WH-008 | Warehouse Operator | Warehouse | no |
| ST-012 | Station Leader | Production | no |
| PM-003 | Production Manager | Production | **yes** |
| LM-001 | Logistics Manager | Logistics | **yes** |

---

## 8. Excel import and Maker-Checker

**Imported data is never definitive until a habilitated checker — a different
person from the maker — has confirmed it inside SLCC.**

```
IMPORTED → PENDING_REVIEW → APPROVED   (rows applied)
                          → REJECTED   (nothing applied, comment mandatory)
```

| Step | Who | Effect |
|------|-----|--------|
| Fills the spreadsheet | MAKER | outside the system |
| Uploads the file | MAKER | file parsed and stored, **no business record, no stock** |
| Reviews | CHECKER | sees every row, valid and invalid |
| **Approves** | CHECKER | rows applied **through the normal services** |
| **Rejects** | CHECKER | nothing applied, reason recorded |

### Segregation of duties

Approval is refused when:

1. the checker **is** the maker — *"the checker must be a different person"*;
2. the checker is **inactive**;
3. the checker's role is **not habilitated** for that import type.

| Import type | May enter (MAKER) | May validate (CHECKER) |
|-------------|-------------------|------------------------|
| Reception | Receptionist, Reception Manager | Reception Manager, Logistics Manager |
| Inspection | Quality Inspector, Quality Manager | **Quality Manager**, Logistics Manager |
| Production request | Station Leader, Production Manager | Production Manager, Logistics Manager |

A Quality Inspector is deliberately **absent** from the inspection checkers: an
inspector can never validate their own inspection as a Quality Manager. The UI
never offers the maker as a candidate checker either.

### What is recorded

`data_imports` plus the `AuditLog` keep:

- maker matricule + role + service + submission timestamp;
- checker matricule + role + service + validation timestamp;
- the decision and the comment (mandatory on rejection);
- the source file name and its **SHA-256 hash**;
- every row verbatim, its status and, once applied, the reference it produced.

No password ever travels through the spreadsheet: validation happens in SLCC by
selecting the responsible, exactly as the specification requires.

Applied rows go through `reception_service`, `inspection_service` and
`production_service` — so the tolerance rule, the sampling rule and the workflow
guards all still apply. **An approved reception still creates only a lot, never
stock**: the stock rule of section 1 is untouched.

---

## 9. Roles

Simulated, not authenticated. The operator picks who they are acting as in
Settings, and that identity is attached to every action in the audit trail.

| Role | Owns |
|------|------|
| Receptionist | receptions and quantity checks |
| Reception Manager | validates reception entries |
| Quality Inspector | sampling and defect recording |
| Quality Manager | approve / reject / Red Cage, validates inspections |
| Warehouse Operator | storage confirmation and issues |
| Station Leader | production requests |
| Production Manager | request validation |
| Logistics Manager | supervision, analytics, alerts, AI |

---

## 10. Configurable settings

All stored in `system_settings`, editable from the Settings screen, effective
immediately, and audited when changed.

| Key | Default | Effect |
|-----|---------|--------|
| `reception.tolerance_percent_small` | 5.0 | tolerance for small parts |
| `reception.tolerance_percent_large` | 0.0 | tolerance for large parts |
| `inspection.sample_percent` | 4.0 | sampling rate |
| `inspection.sample_minimum` | 5 | minimum sample size |
| `inspection.defect_threshold_percent` | 2.0 | conformity threshold |
| `warehouse.warning_occupancy_percent` | 75.0 | address nearly full |
| `warehouse.critical_occupancy_percent` | 90.0 | address saturated |
| `ai.shortage_cover_days_high` | 2.0 | high shortage risk |
| `ai.shortage_cover_days_medium` | 5.0 | medium shortage risk |
| `ai.blocked_lot_hours` | 24.0 | blocked-lot escalation |
