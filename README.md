# Smart Logistics Control Center (SLCC)

Web platform for supervising the flow of parts from supplier delivery to
consumption in production:

**Supplier → Receiving → Inspection → Quality → Warehouse → Production**

| Layer | Stack |
|-------|-------|
| Frontend | React 18 · TypeScript · Vite · TailwindCSS · React Router · Framer Motion · Lucide · Axios |
| Backend | Python · FastAPI · SQLAlchemy 2 · Pydantic v2 · Alembic |
| Database | PostgreSQL (automatic SQLite fallback in development) |
| Analytics | Flat datasets + DAX measures exposed for Power BI |
| Decision support | Deterministic, fully explained analysis engine + Logistics Copilot |

---

## The stock rule

This is the backbone of the whole system and it is enforced in the service layer,
covered by tests, and impossible to bypass from the UI.

```
IN    Reception → Inspection → Quality validation → Storage confirmed → STOCK +
OUT   Request   → Validation → Preparation        → Issue confirmed   → STOCK -
```

- A reception, an inspection, a quality approval or a production request **never**
  changes the stock balance.
- Only `POST /lots/{id}/storage/confirm` increments stock.
- Only `POST /production/requests/{id}/issue` decrements it.
- Every change writes a **StockMovement** and an **AuditLog** in the same
  transaction — either both land or neither does.
- Stock can never go negative: refused in the service, and a `CHECK` constraint in
  the database is the last line of defence.

See [`backend/app/services/stock_service.py`](backend/app/services/stock_service.py)
and the tests in [`backend/tests/test_stock_rules.py`](backend/tests/test_stock_rules.py).

---

## Modules

| Screen | What it does |
|--------|--------------|
| **Mission Control** | Live KPIs, the six-stage animated flow, smart alerts, activity feed, Copilot, one-click end-to-end simulation |
| **Data Import** | Excel/CSV entry by an identified operator (MAKER), validated by a habilitated responsible (CHECKER) before anything enters the system |
| **Receiving** | Books deliveries in; previews the applicable tolerance rule before confirming |
| **Inspection** | Server-computed sampling plan, defect recording, automatic routing to quality or Red Cage |
| **Quality** | Approve / reject / quarantine, Red Cage management, full decision history — every decision requires a justification |
| **Warehouse** | Interactive address map, storage confirmation (with split across secondary addresses), live stock table |
| **Production** | Full request workflow DRAFT → ISSUED with live stock coverage per request |
| **Traceability** | Lot history, audit-trail search, per-reference stock ledger |
| **Analytics** | Stock, flow, quality, production indicators, bottleneck detection, Power BI datasets |
| **AI Assistant** | Shortage risk, prioritisation, optimisation — each with its reasoning — plus the Copilot |
| **Settings** | Business thresholds (tolerance, sampling, saturation), reference data, simulated operator |

---

## Business rules implemented

- **Reception tolerance** — configurable, never hardcoded. SMALL parts accept a
  percentage deviation (default 5%), LARGE parts require an exact count, and a part
  can carry its own override. A delivery outside tolerance is quarantined.
- **Sampling** — sample size = `max(minimum, ceil(quantity × rate))`, capped by the
  lot size. Rate, floor and defect threshold are all settings.
- **Red Cage** — quarantine for a non-conform inspection *or* an out-of-tolerance
  reception; a lot leaves it only through a justified decision (release or scrap).
- **Addressing** — one primary address per reference plus secondary addresses; a
  lot too large for its primary address is split, and the backend proposes how.
- **Operator identification** — every operator has a unique employee number
  (matricule), a role, a service and an active flag. No action is ever anonymous.
- **Maker-Checker** — data imported from a spreadsheet stays in `PENDING_REVIEW`
  until a habilitated responsible, **never the maker**, approves it in SLCC. A
  rejection requires a comment and applies nothing. The maker, the checker, both
  roles, both timestamps, the decision, the comment, the file name and its SHA-256
  hash are all recorded.
- **Roles** — eight simulated roles; the acting operator is recorded on every action.
- **Audit** — who, what, when, how much, which lot, which reference, which location,
  status before, status after, why.

---

## Getting started

### 0. Environment

```bash
cp .env.example .env
```

### 1. Backend

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows
pip install -r backend/requirements.txt

cd backend
alembic upgrade head              # create the schema
python scripts/seed.py --reset    # demonstration dataset
uvicorn app.main:app --reload --port 8000
```

- API: <http://127.0.0.1:8000> · Swagger: <http://127.0.0.1:8000/docs>
- Health: <http://127.0.0.1:8000/api/health>

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Application: <http://localhost:5173>.
If the backend runs on another port, set `VITE_API_BASE_URL` in `frontend/.env.local`.

### 3. PostgreSQL (target engine)

```bash
psql -U postgres -f database/init/01_create_database.sql
# set DATABASE_URL in .env, then:
cd backend
alembic upgrade head
python scripts/seed.py --reset
python scripts/audit.py            # 87 checks against the running API
```

**SQLite is a development fallback only.** If PostgreSQL is unreachable *and*
`ENVIRONMENT` is a development one, the API degrades to a local SQLite file and
says so on `GET /api/health/db` (`"fallback": true`). Outside development the
fallback is refused and the failure surfaces — silently writing stock movements
to a local file while the real database is down would corrupt the inventory
record. Set `DATABASE_FALLBACK_SQLITE=false` to disable it even in development.

Alembic resolves the same URL the application resolved, so `alembic upgrade head`
works in both cases. To render the DDL for a PostgreSQL server without connecting:

```bash
alembic upgrade head --sql > schema.sql
python scripts/check_postgres_compat.py   # schema + queries compile for PostgreSQL
```

---

## The demonstration

`Mission Control → Run simulation` executes the whole chain through the real
services and shows each step with its effect on stock:

```
truck arrives → reception → inspection → quality → storage (STOCK +)
              → production request → approval → preparation → issue (STOCK -)
```

Use **Stop after** to run it step by step and narrate the demo. Every step is
visible immediately in Mission Control, Warehouse, Traceability, Analytics and the
AI Assistant. Full script: [`docs/DEMO.md`](docs/DEMO.md).

---

## Scripts

| Command | Location | Purpose |
|---------|----------|---------|
| `npm run dev` | `frontend/` | dev server with HMR |
| `npm run build` | `frontend/` | typecheck + production build |
| `uvicorn app.main:app --reload` | `backend/` | API with auto-reload |
| `pytest tests -q` | `backend/` | test suite (81 tests) |
| `alembic upgrade head` | `backend/` | apply migrations |
| `python scripts/seed.py --reset` | `backend/` | rebuild the demonstration dataset |
| `python scripts/audit.py` | `backend/` | end-to-end audit of the running API (87 checks) |
| `python scripts/check_postgres_compat.py` | `backend/` | prove the schema and queries are PostgreSQL compatible |

---

## API

66 endpoints, documented at `/docs`. The main ones:

| Method | Route | Effect on stock |
|--------|-------|-----------------|
| POST | `/api/imports` | none — upload awaiting validation |
| POST | `/api/imports/{id}/approve` | none directly — applies the rows |
| POST | `/api/receptions` | none |
| POST | `/api/lots/{id}/inspect` | none |
| POST | `/api/lots/{id}/quality/approve` | none |
| POST | `/api/lots/{id}/storage/confirm` | **+** |
| POST | `/api/production/requests` | none |
| POST | `/api/production/requests/{id}/approve` | none (reserves) |
| POST | `/api/production/requests/{id}/issue` | **−** |
| GET | `/api/dashboard` | Mission Control payload |
| GET | `/api/traceability/lots/{id}` | full lot history |
| GET | `/api/analytics` · `/api/analytics/powerbi` | indicators and BI datasets |
| GET | `/api/ai/analysis` · POST `/api/ai/copilot` | decision support |
| POST | `/api/simulation/run` | runs the whole chain |

---

## Documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — layers and conventions
- [`docs/DATA_MODEL.md`](docs/DATA_MODEL.md) — entities, relations, state machines
- [`docs/BUSINESS_RULES.md`](docs/BUSINESS_RULES.md) — every rule and where it lives
- [`docs/DESIGN_SYSTEM.md`](docs/DESIGN_SYSTEM.md) — colours, surfaces, motion
- [`docs/DEMO.md`](docs/DEMO.md) — the demonstration script
- [`docs/POWERBI.md`](docs/POWERBI.md) — connecting Power BI (REST or direct PostgreSQL)
- [`database/powerbi_views.sql`](database/powerbi_views.sql) — analytical SQL views for Power BI
- [`docs/PHASE1.md`](docs/PHASE1.md) — foundation phase log
- [`PROJECT_SLCC.md`](PROJECT_SLCC.md) — functional specification
