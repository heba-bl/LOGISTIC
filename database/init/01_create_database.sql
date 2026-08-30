-- Smart Logistics Control Center - database bootstrap
-- Usage: psql -U postgres -f database/init/01_create_database.sql
--
-- Tables are created by Alembic (cd backend && alembic upgrade head),
-- this script only provisions the database itself.

SELECT 'CREATE DATABASE smart_logistics'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'smart_logistics')\gexec

\connect smart_logistics

COMMENT ON DATABASE smart_logistics IS 'Smart Logistics Control Center (SLCC)';
