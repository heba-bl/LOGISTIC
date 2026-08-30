# Power BI integration

Power BI is the **analysis** layer, not the operational one. The application acts;
Power BI reports. Nothing in SLCC depends on Power BI being connected — if it never
is, every screen keeps working.

```
React → FastAPI → PostgreSQL → Power BI
```

---

## Connecting

### Option A - REST endpoint (fastest, good for the demonstration)

`GET /api/analytics/powerbi` returns every dataset in one JSON payload.

**Power BI Desktop → Get Data → Web**, then paste:

```
http://127.0.0.1:8000/api/analytics/powerbi
```

Expand `datasets`, then the `rows` of the table you want. The Analytics screen has
a **Power BI datasets** button that shows the endpoint, the datasets, their row and
column counts, and the suggested measures.

### Option B - direct PostgreSQL connection (recommended for the real model)

The SQL equivalents of every dataset ship as views in
[`database/powerbi_views.sql`](../database/powerbi_views.sql).

```bash
# 1. Install the analytical views (once)
psql -U postgres -d smart_logistics -f database/powerbi_views.sql

# 2. Optional: a read-only login for the BI tool
#    (uncomment the powerbi_reader block at the end of the file first)
```

Then in Power BI Desktop:

1. **Get Data → PostgreSQL database**
2. Server `localhost`, Database `smart_logistics`
3. Data Connectivity mode: **Import** (or DirectQuery for live figures)
4. In the navigator, expand the **analytics** schema and select:
   `vw_fact_lots`, `vw_fact_stock_movements`, `vw_fact_quality`,
   `vw_fact_production_requests`, `vw_dim_stock`, `vw_dim_locations`, `vw_dim_date`
   (the JSON endpoint exposes the same seven tables, `dim_date` included)
5. **Load**, then in Model view create the relationships:

| From | To | Cardinality |
|------|----|-------------|
| `vw_fact_stock_movements[part_reference]` | `vw_dim_stock[part_reference]` | many-to-one |
| `vw_fact_stock_movements[occurred_on]` | `vw_dim_date[date]` | many-to-one |
| `vw_fact_stock_movements[location]` | `vw_dim_locations[location_code]` | many-to-one |
| `vw_fact_lots[part_reference]` | `vw_dim_stock[part_reference]` | many-to-one |
| `vw_fact_quality[part_reference]` | `vw_dim_stock[part_reference]` | many-to-one |
| `vw_fact_production_requests[part_reference]` | `vw_dim_stock[part_reference]` | many-to-one |

Mark `vw_dim_date` as the date table (`date` column) so time intelligence works.

The views add columns the JSON endpoint does not carry, precisely to make the BI
model easier: `signed_quantity` (so a running total gives the stock on hand),
`is_conform`, `days_of_cover`, `hours_to_storage`, `hours_to_issue`,
`occupancy_state` and `stock_state`.

The schema itself is documented in [`DATA_MODEL.md`](DATA_MODEL.md).

---

## Datasets

Deliberately flat and denormalised: one row per fact, every dimension already
resolved, so the model is useful without a single join.

| Dataset | Grain | Key columns |
|---------|-------|-------------|
| `fact_lots` | one row per lot | lot_number, part_reference, supplier, status, quantities, location, received_at, stored_at |
| `fact_stock_movements` | one row per movement | movement_reference, movement_type, part_reference, quantity, quantity_before, quantity_after, actor, occurred_at, reason |
| `fact_quality` | one row per inspection | inspection_reference, lot_number, part_reference, supplier, sample_size, defects_found, defect_rate_percent, result |
| `fact_production_requests` | one row per request | request_reference, station, production_line, part_reference, quantity_requested, quantity_issued, status, priority |
| `dim_stock` | one row per reference | part_reference, designation, category, quantity_available, quantity_reserved, safety_stock, average_daily_consumption |
| `dim_locations` | one row per address | location_code, zone, capacity, occupied, occupancy_percent |

---

## Suggested measures (DAX)

The API serves the same list at `/api/analytics/powerbi`, so the report and the
application always agree on a definition.

```dax
Total Stock = SUM(dim_stock[quantity_available])

Stock Coverage =
DIVIDE([Total Stock], SUM(dim_stock[average_daily_consumption]))

Conformity Rate =
DIVIDE(
    CALCULATE(COUNTROWS(fact_quality), fact_quality[result] = "CONFORM"),
    COUNTROWS(fact_quality)
)

Non-Conformity Rate = 1 - [Conformity Rate]

Blocked Lots =
CALCULATE(COUNTROWS(fact_lots), fact_lots[status] = "RED_CAGE")

Warehouse Occupancy =
DIVIDE(SUM(dim_locations[occupied]), SUM(dim_locations[capacity]))

Issued Quantity = SUM(fact_production_requests[quantity_issued])

-- A cancelled or rejected request was never meant to be served. Leaving it in
-- the denominator sinks the service rate on a decision that was taken
-- deliberately, and hides a real supply problem behind it. The API applies the
-- same exclusion.
Service Rate =
VAR Servable =
    FILTER(
        fact_production_requests,
        NOT fact_production_requests[status] IN { "CANCELLED", "REJECTED" }
    )
RETURN
    DIVIDE(
        SUMX(Servable, fact_production_requests[quantity_issued]),
        SUMX(Servable, fact_production_requests[quantity_requested])
    )

Open Demand =
CALCULATE(
    SUM(fact_production_requests[quantity_outstanding]),
    fact_production_requests[status]
        IN { "SUBMITTED", "APPROVED", "PREPARING", "READY" }
)

References At Risk =
COUNTROWS(
    FILTER(
        VALUES(dim_stock[part_reference]),
        CALCULATE(SUM(dim_stock[quantity_available])) < [Open Demand]
    )
)
```

---

## Report theme

Download `GET /api/analytics/powerbi/theme.json` (or the button on the
**Analyse** screen), then **View -> Themes -> Browse for themes**. The report
then carries exactly the colours of the application.

| Role | Hex | Used for |
|------|-----|----------|
| Deep Petrol | `#173F4F` | primary information, series 1 |
| Muted Teal | `#5F9EA0` | healthy state, series 2 |
| Deep Sand | `#C9A96A` | attention, series 3 |
| Clay | `#A0524A` | urgent, series 4 |
| Slate Blue | `#496A78` | comparison |
| Soft Aqua | `#8FC7C5` | secondary information |
| Soft Cream | `#F4F1EA` | page background |
| Deep Navy | `#172A35` | text |

The palette is deliberately muted and contains no pure red: a saturated report
read all day becomes noise. Colour never carries a value on its own - every
mark is direct-labelled, in Power BI as in the application.

---

## Suggested report pages

| Page | Content |
|------|---------|
| **Stock** | stock by category, by reference, by address; occupancy; evolution over time |
| **Flow** | lots received / inspected / validated / blocked; average time between stages; bottleneck |
| **Quality** | conformity and non-conformity rate, Red Cage count, defects by reference and by supplier |
| **Production** | requests per station, quantities requested vs issued, pending requests, consumption |

The same indicators are already computed by `GET /api/analytics` and rendered on
the in-app Analytics screen, so the two layers agree by construction.

---

## Checking the model

The ledger must reconcile with the stock table. The query at the end of
`powerbi_views.sql` returns **zero rows** when the model is consistent:

```sql
SELECT d.part_reference, d.quantity_available, COALESCE(SUM(m.signed_quantity), 0)
FROM analytics.vw_dim_stock d
LEFT JOIN analytics.vw_fact_stock_movements m ON m.part_reference = d.part_reference
GROUP BY d.part_reference, d.quantity_available
HAVING d.quantity_available <> COALESCE(SUM(m.signed_quantity), 0);
```

The same invariant is asserted on the API side by `scripts/audit.py`
("dim_stock agrees with the API").

## Refresh

The endpoint reads the live database on every call, so a Power BI scheduled refresh
picks up the current state. For large histories, prefer a direct PostgreSQL
connection with incremental refresh on `fact_stock_movements.occurred_at`.
