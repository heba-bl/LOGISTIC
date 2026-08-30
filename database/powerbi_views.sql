-- ---------------------------------------------------------------------------
-- Smart Logistics Control Center - Power BI analytical views (PostgreSQL)
--
-- These views are the SQL equivalent of the datasets returned by
-- GET /api/analytics/powerbi. Use them when connecting Power BI directly to
-- PostgreSQL (recommended for large histories and scheduled refresh); use the
-- API endpoint for a quick demonstration.
--
-- Install:
--     psql -U postgres -d smart_logistics -f database/powerbi_views.sql
--
-- Then in Power BI Desktop: Get Data -> PostgreSQL database -> select the
-- six vw_* views below.
-- ---------------------------------------------------------------------------

CREATE SCHEMA IF NOT EXISTS analytics;

-- ---------------------------------------------------------------------------
-- FACT: lots and their position in the flow
-- Grain: one row per lot.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW analytics.vw_fact_lots AS
SELECT
    l.lot_number,
    p.reference                       AS part_reference,
    p.designation                     AS part_designation,
    c.name                            AS category,
    s.name                            AS supplier,
    s.code                            AS supplier_code,
    s.country                         AS supplier_country,
    l.status,
    l.quantity_expected,
    l.quantity_received,
    l.quantity_approved,
    l.quantity_available,
    wl.code                           AS location,
    wl.zone                           AS location_zone,
    l.received_at,
    l.stored_at,
    l.blocked_reason,
    -- Hours spent between arrival and physical storage (NULL while not stored).
    EXTRACT(EPOCH FROM (l.stored_at - l.received_at)) / 3600.0 AS hours_to_storage
FROM lots l
JOIN parts p                ON p.id = l.part_id
JOIN suppliers s            ON s.id = l.supplier_id
LEFT JOIN categories c      ON c.id = p.category_id
LEFT JOIN warehouse_locations wl ON wl.id = l.location_id;

-- ---------------------------------------------------------------------------
-- FACT: the stock ledger
-- Grain: one row per stock movement. This is the accounting record behind the
-- current stock value: SUM(signed_quantity) per part equals the stock on hand.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW analytics.vw_fact_stock_movements AS
SELECT
    m.reference                       AS movement_reference,
    m.movement_type,
    p.reference                       AS part_reference,
    c.name                            AS category,
    m.quantity,
    CASE WHEN m.movement_type = 'IN' THEN m.quantity ELSE -m.quantity END AS signed_quantity,
    m.quantity_before,
    m.quantity_after,
    l.lot_number,
    wl.code                           AS location,
    st.code                           AS station,
    pr.reference                      AS request_reference,
    m.actor_name                      AS actor,
    m.reason,
    m.occurred_at,
    m.occurred_at::date               AS occurred_on
FROM stock_movements m
JOIN parts p                     ON p.id = m.part_id
LEFT JOIN categories c           ON c.id = p.category_id
LEFT JOIN lots l                 ON l.id = m.lot_id
LEFT JOIN warehouse_locations wl ON wl.id = m.location_id
LEFT JOIN production_stations st ON st.id = m.station_id
LEFT JOIN production_requests pr ON pr.id = m.production_request_id;

-- ---------------------------------------------------------------------------
-- FACT: quality inspections
-- Grain: one row per inspection.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW analytics.vw_fact_quality AS
SELECT
    i.reference                       AS inspection_reference,
    l.lot_number,
    p.reference                       AS part_reference,
    c.name                            AS category,
    s.name                            AS supplier,
    i.sample_size,
    i.defects_found,
    i.defect_threshold_percent,
    CASE
        WHEN i.sample_size > 0
        THEN ROUND((i.defects_found::numeric / i.sample_size) * 100, 2)
        ELSE 0
    END                               AS defect_rate_percent,
    i.result,
    CASE WHEN i.result = 'CONFORM' THEN 1 ELSE 0 END AS is_conform,
    i.observations,
    i.inspected_at,
    i.inspected_at::date              AS inspected_on
FROM inspections i
JOIN lots l                 ON l.id = i.lot_id
JOIN parts p                ON p.id = l.part_id
JOIN suppliers s            ON s.id = l.supplier_id
LEFT JOIN categories c      ON c.id = p.category_id;

-- ---------------------------------------------------------------------------
-- FACT: production demand and issues
-- Grain: one row per production request.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW analytics.vw_fact_production_requests AS
SELECT
    pr.reference                      AS request_reference,
    st.code                           AS station,
    st.name                           AS station_name,
    st.production_line,
    p.reference                       AS part_reference,
    c.name                            AS category,
    pr.quantity_requested,
    pr.quantity_issued,
    pr.quantity_requested - pr.quantity_issued AS quantity_outstanding,
    pr.status,
    pr.priority,
    pr.created_on,
    pr.submitted_at,
    pr.approved_at,
    pr.issued_at,
    -- Hours between the request and the physical issue (NULL while not issued).
    EXTRACT(EPOCH FROM (pr.issued_at - pr.created_on)) / 3600.0 AS hours_to_issue
FROM production_requests pr
JOIN production_stations st ON st.id = pr.station_id
JOIN parts p                ON p.id = pr.part_id
LEFT JOIN categories c      ON c.id = p.category_id;

-- ---------------------------------------------------------------------------
-- DIM: current stock per reference
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW analytics.vw_dim_stock AS
SELECT
    p.reference                       AS part_reference,
    p.designation,
    COALESCE(c.name, 'Uncategorised') AS category,
    p.size_class,
    p.unit,
    COALESCE(stk.quantity_available, 0) AS quantity_available,
    COALESCE(stk.quantity_reserved, 0)  AS quantity_reserved,
    GREATEST(COALESCE(stk.quantity_available, 0) - COALESCE(stk.quantity_reserved, 0), 0)
                                      AS quantity_free,
    p.safety_stock,
    p.average_daily_consumption,
    CASE
        WHEN p.average_daily_consumption > 0
        -- Cast to numeric: PostgreSQL has no round(double precision, int).
        THEN ROUND(
            COALESCE(stk.quantity_available, 0)::numeric
            / p.average_daily_consumption::numeric, 1)
        ELSE NULL
    END                               AS days_of_cover,
    CASE
        WHEN COALESCE(stk.quantity_available, 0) < p.safety_stock THEN 'BELOW_SAFETY'
        ELSE 'OK'
    END                               AS stock_state,
    stk.last_movement_at
FROM parts p
LEFT JOIN stock stk    ON stk.part_id = p.id
LEFT JOIN categories c ON c.id = p.category_id
WHERE p.is_active;

-- ---------------------------------------------------------------------------
-- DIM: warehouse addresses and occupancy
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW analytics.vw_dim_locations AS
SELECT
    wl.code                           AS location_code,
    w.code                            AS warehouse_code,
    wl.zone,
    wl.position,
    wl.capacity,
    wl.occupied,
    GREATEST(wl.capacity - wl.occupied, 0) AS free_capacity,
    CASE
        WHEN wl.capacity > 0
        THEN ROUND((wl.occupied::numeric / wl.capacity) * 100, 1)
        ELSE 0
    END                               AS occupancy_percent,
    wl.warning_threshold_percent,
    wl.critical_threshold_percent,
    CASE
        WHEN wl.capacity = 0 THEN 'OK'
        WHEN (wl.occupied::numeric / wl.capacity) * 100 >= wl.critical_threshold_percent
            THEN 'CRITICAL'
        WHEN (wl.occupied::numeric / wl.capacity) * 100 >= wl.warning_threshold_percent
            THEN 'WARNING'
        ELSE 'OK'
    END                               AS occupancy_state,
    wl.is_active
FROM warehouse_locations wl
JOIN warehouses w ON w.id = wl.warehouse_id;

-- ---------------------------------------------------------------------------
-- DIM: date spine, so Power BI time intelligence works out of the box.
-- Covers the full range of recorded movements.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW analytics.vw_dim_date AS
SELECT
    d::date                                   AS date,
    EXTRACT(YEAR    FROM d)::int              AS year,
    EXTRACT(QUARTER FROM d)::int              AS quarter,
    EXTRACT(MONTH   FROM d)::int              AS month,
    TO_CHAR(d, 'YYYY-MM')                     AS year_month,
    TO_CHAR(d, 'Mon')                         AS month_name,
    EXTRACT(WEEK FROM d)::int                 AS week,
    EXTRACT(ISODOW FROM d)::int               AS day_of_week,
    TO_CHAR(d, 'Dy')                          AS day_name
FROM generate_series(
    COALESCE((SELECT MIN(occurred_at)::date FROM stock_movements), CURRENT_DATE - 30),
    COALESCE((SELECT MAX(occurred_at)::date FROM stock_movements), CURRENT_DATE),
    INTERVAL '1 day'
) AS d;

-- ---------------------------------------------------------------------------
-- Read-only role for the BI tool.
-- Replace the password before running this in anything but a demo.
-- ---------------------------------------------------------------------------
-- CREATE ROLE powerbi_reader LOGIN PASSWORD 'change_me';
-- GRANT CONNECT ON DATABASE smart_logistics TO powerbi_reader;
-- GRANT USAGE ON SCHEMA analytics, public TO powerbi_reader;
-- GRANT SELECT ON ALL TABLES IN SCHEMA analytics TO powerbi_reader;
-- GRANT SELECT ON ALL TABLES IN SCHEMA public TO powerbi_reader;
-- ALTER DEFAULT PRIVILEGES IN SCHEMA analytics GRANT SELECT ON TABLES TO powerbi_reader;

-- ---------------------------------------------------------------------------
-- Sanity check: the ledger must reconcile with the stock table.
-- Both columns must be equal for every reference.
-- ---------------------------------------------------------------------------
-- SELECT
--     d.part_reference,
--     d.quantity_available                       AS stock_table,
--     COALESCE(SUM(m.signed_quantity), 0)        AS ledger_balance
-- FROM analytics.vw_dim_stock d
-- LEFT JOIN analytics.vw_fact_stock_movements m
--        ON m.part_reference = d.part_reference
-- GROUP BY d.part_reference, d.quantity_available
-- HAVING d.quantity_available <> COALESCE(SUM(m.signed_quantity), 0);
