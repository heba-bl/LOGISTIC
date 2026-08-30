# Architecture

## Principles

1. **Layer separation.** The API never talks to SQLAlchemy directly: a route
   calls a service, a service calls a repository, a repository owns the query.
2. **Typed boundaries.** Pydantic on the backend, TypeScript on the frontend.
   A payload shape is declared once and reused.
3. **Environment driven.** No hardcoded URL, port or credential in the code.
4. **Feature-oriented frontend.** A screen owns its folder under `features/`;
   `components/` only holds what is genuinely reusable.

---

## Backend

```
app/
├── main.py             application factory, CORS, domain-error handler
├── api/
│   ├── deps.py         session dependency (rollback on failure)
│   ├── router.py       aggregates every feature router
│   └── routes/         health · catalog · receiving · lots · warehouse
│                       production · insights
├── schemas/            Pydantic — the HTTP contract
├── services/           business rules — one module per capability:
│                       reception · inspection · quality · warehouse
│                       production · stock · audit · settings · reference
│                       dashboard · traceability · analytics · ai
│                       copilot · simulation
├── repositories/       data access, one per aggregate
├── models/             SQLAlchemy models (19 tables)
├── db/
│   ├── base.py         DeclarativeBase + naming conventions
│   └── session.py      engine, SessionLocal, get_db, health state
└── core/
    ├── config.py       Settings (pydantic-settings)
    ├── exceptions.py   domain errors mapped to HTTP status codes
    ├── timeutils.py    UTC normalisation for display
    └── logging.py      logging setup
```

### Error handling

Services never import FastAPI. They raise domain errors
(`WorkflowError`, `ValidationError`, `InsufficientStockError`, `CapacityError`,
`NotFoundError`) and a single handler in `main.py` maps them to status codes with a
stable body: `{code, message, details}`. A refused operation therefore reads the
same way in the API, in the tests and in the UI toast.

### Transactions

`api/deps.get_session` yields a session and rolls back if the request raises.
Routes commit explicitly once the business operation succeeded, so a stock change
and the movement plus audit entry that justify it are always atomic.

### Request path

```
HTTP → route (api/routes) → service → repository → SQLAlchemy → PostgreSQL
                ↑                                        ↓
            schema (Pydantic) ←──────────────────── model (ORM)
```

### Database connection

`db/session.py` builds the engine at startup and probes it with `SELECT 1`.
If PostgreSQL is unreachable and `DATABASE_FALLBACK_SQLITE=true`, it switches to
a local SQLite file and records the reason in `db_state`. `GET /api/health/db`
always reports the backend actually in use — a degraded mode is never silent.

### Migrations

Alembic reads its URL from `app.core.config`, so migrations and the running API
can never target different databases. A constraint naming convention is declared
on `Base.metadata` so autogenerate produces stable names.

---

## Frontend

```
src/
├── main.tsx            React root + BrowserRouter + Toast/Actor providers
├── App.tsx             route table
├── layouts/            AppLayout, Sidebar, Topbar, navigation.ts
├── pages/              one component per route (10 modules + 404)
├── features/
│   ├── mission-control/  KPIs, flow, alerts, activity, copilot
│   ├── traceability/     lot detail drawer (used by every screen)
│   ├── analytics/        charts
│   └── simulation/       demonstration driver
├── components/ui/      Panel, Badge, StatusDot, Meter, Modal, controls
├── services/           axios instance + one typed function per endpoint
├── hooks/              useApiResource, useApiHealth, useActor, useToast, useClock
├── types/              domain.ts mirrors the backend schemas
└── utils/              cn, format, status mapping
```

### Data fetching

`useApiResource(fetcher, deps, {pollMs})` returns `{data, loading, initialLoading,
error, refresh}`. `initialLoading` is separate from `loading` so a refresh never
blanks the screen. After any write the page calls `refresh()`, so the UI shows what
the backend actually recorded rather than an optimistic guess.

### Identity

Roles are simulated. `useActor` holds the selected operator and every write sends
its `actor_id`, so the audit trail records a real name. Each screen preselects the
role that owns it (the reception form acts as the Receptionist, storage as the
Warehouse Operator, and so on).

### Frontend ↔ backend

`services/apiClient.ts` holds one Axios instance configured from
`VITE_API_BASE_URL`. `hooks/useApiHealth` polls `GET /api/health` every 15s and
drives the status indicators in the topbar and on Mission Control — so the
"Operational" badge reflects the real backend, not a hardcoded value.

### Data flow

Every screen reads live data. `GET /api/dashboard` returns the whole Mission
Control payload in one round trip (KPIs, stages, lots, alerts, activity), polled
every 30 seconds and refreshed on demand. There are no fixtures left in the
frontend.

---

## Conventions

| Topic | Rule |
|-------|------|
| Routes | kebab-case (`/mission-control`) |
| React components | PascalCase, one component per file |
| Python | snake_case, type hints everywhere, `from __future__ import annotations` |
| Commits | present tense, scoped (`backend: add health endpoint`) |
| Status colours | green = normal, orange = attention, red = critical, blue = information |
