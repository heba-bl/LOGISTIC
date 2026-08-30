# Phase 1 — Foundation

Goal: a clean, evolvable foundation and a first credible Mission Control
interface. **No business feature is implemented in this phase.**

## Delivered

### Structure
- `frontend/`, `backend/`, `database/`, `docs/` + `.env.example`, `.gitignore`
- Frontend split: `components/ layouts/ pages/ features/ services/ hooks/ types/ utils/`
- Backend split: `api/ models/ schemas/ services/ repositories/ core/ db/`

### Backend
- FastAPI application factory with lifespan logging
- `GET /api/health` → `{"status": "ok", "service": "smart-logistics-api"}`
- `GET /api/health/db`, `GET /api/info`, Swagger at `/docs`
- CORS configured from `ALLOWED_ORIGINS`
- Settings via `pydantic-settings`, `.env` driven
- SQLAlchemy 2 engine/session + `get_db` dependency, with a reported SQLite
  fallback when PostgreSQL is unreachable
- Alembic wired to the app settings; baseline migration `0001_baseline` (empty)
- `BaseRepository` generic to seed the data-access pattern
- pytest suite covering the API surface

### Frontend
- Vite + React 18 + TypeScript (strict, `noUnusedLocals`)
- TailwindCSS design system (industrial dark navy, functional colour palette)
- React Router with all ten routes + 404, driven by a single `NAV_ITEMS` list
- Framer Motion: entry stagger, route transitions, animated flow, nav spring
- Axios service layer + `useApiHealth` polling the real backend
- Sidebar ("Smart Logistics / Control Center") and topbar with live API status

### Mission Control
- Header with a system status badge driven by the real health check
- 6 KPI tiles: Total Stock, Active Lots, Pending Inspections, Production
  Requests, Warehouse Occupancy (with meter), Critical Alerts
- **Live Logistics Flow**: the six stages with animated connectors, per-stage
  quantities and the lots currently sitting at each stage
- **Lots in Flow**: five demo lots across four different statuses
- **Smart Alerts**: critical / warning / info
- **Recent Activity**: chronological trace
- **Logistics Copilot**: visual surface only, input disabled, marked "Phase 3"

## Explicitly NOT in this phase

Real lot management · real stock · real inspections · real production requests ·
AI · Power BI · full role system · complete business schema.

## Demo data

All Mission Control figures come from `frontend/src/features/mission-control/data.ts`
and are frontend-only. Components are typed against `types/logistics.ts`, so
Phase 2 swaps the fixture import for an API call without touching the UI.

## Verification performed

| Check | Result |
|-------|--------|
| `npm install` | ok |
| `npm run build` (tsc + vite) | ok, 0 TypeScript errors |
| `pytest tests -q` | 4 passed |
| `GET /api/health` | exact expected contract |
| `GET /api/health/db`, `/api/info`, `/docs` | ok |
| CORS preflight from `http://localhost:5173` | allowed |
| `alembic upgrade head` | applied |
| 12 frontend routes over HTTP | all 200 |
| Headless render of `/mission-control` and a placeholder | all sections present |
| Frontend → backend live call | topbar shows "API Online" |

## Next — Phase 2

Business data model (suppliers, parts, lots, receptions, inspections, quality
validations, stock, movements, production requests, audit log), migration
`0002`, CRUD endpoints, and the Receiving / Inspection / Quality / Warehouse /
Production modules.
