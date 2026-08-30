# Database — Smart Logistics Control Center

Target engine: **PostgreSQL 14+**. The schema itself is owned by Alembic
(`backend/alembic/versions/`), never by hand-written SQL.

## 1. Create the database

With `psql` available:

```bash
psql -U postgres -f database/init/01_create_database.sql
```

Or manually:

```sql
CREATE DATABASE smart_logistics;
```

## 2. Point the API at it

In `.env` (repository root):

```
DATABASE_URL=postgresql+psycopg2://postgres:<password>@localhost:5432/smart_logistics
```

## 3. Apply migrations

```bash
cd backend
alembic upgrade head
```

## Development fallback

SQLite is a **development convenience only**. The fallback triggers when all of
the following hold:

1. PostgreSQL is unreachable at startup;
2. `DATABASE_FALLBACK_SQLITE=true` (default);
3. `ENVIRONMENT` is a development one (`development`, `dev`, `local`).

Outside development the fallback is refused: the API reports the failure instead
of silently writing stock movements to a local file while the real database is
down. The engine actually in use is always reported by `GET /api/health/db`
(`"fallback": true` when degraded), and `tests/test_health.py` asserts this.

Alembic resolves the same URL, so `alembic upgrade head` targets whichever
database the application is actually using.

## Power BI

`powerbi_views.sql` installs the analytical views consumed by Power BI:

```bash
psql -U postgres -d smart_logistics -f database/powerbi_views.sql
```

See [`../docs/POWERBI.md`](../docs/POWERBI.md) for the full procedure.

## Schema status

| Phase | Content |
|-------|---------|
| Phase 1 | `0001_baseline` — empty baseline, no business tables |
| Phase 2 | suppliers, parts, lots, receptions, inspections, quality validations, stock, stock movements, production requests, audit log |
