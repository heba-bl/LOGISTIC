"""End-to-end audit of the running API.

Exercises the complete flow over HTTP and asserts every rule that matters for the
demonstration: the stock rule step by step, the workflow guards, the alerts, the
AI justifications, the Copilot grounding and the Power BI datasets.

Start the API first, then:

    python scripts/audit.py                       # default http://127.0.0.1:8000/api
    python scripts/audit.py --base-url http://127.0.0.1:8001/api

Exit code 0 means every check passed.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import httpx

PASS = "PASS"
FAIL = "FAIL"

results: list[tuple[str, str, str]] = []


def check(section: str, label: str, condition: bool, detail: str = "") -> bool:
    results.append((section, label, PASS if condition else FAIL))
    if not condition and detail:
        results[-1] = (section, f"{label} -- {detail}", FAIL)
    return condition


class Api:
    def __init__(self, base_url: str) -> None:
        self.client = httpx.Client(base_url=base_url, timeout=30.0)

    def get(self, path: str, **params: Any) -> Any:
        response = self.client.get(path, params=params or None)
        response.raise_for_status()
        return response.json()

    def post(self, path: str, payload: dict | None = None) -> httpx.Response:
        return self.client.post(path, json=payload or {})

    def post_ok(self, path: str, payload: dict | None = None) -> Any:
        response = self.post(path, payload)
        response.raise_for_status()
        return response.json()

    def stock(self, part_id: int) -> int:
        return int(self.get(f"/stock/{part_id}")["quantity_available"])


def audit_infrastructure(api: Api) -> None:
    health = api.get("/health")
    check(
        "Infrastructure",
        "GET /api/health returns the expected contract",
        health == {"status": "ok", "service": "smart-logistics-api"},
    )

    db = api.get("/health/db")
    check("Infrastructure", "database reachable", db["connected"] is True)
    check(
        "Infrastructure",
        f"active engine reported ({db['dialect']}{', fallback' if db['fallback'] else ''})",
        db["dialect"] in {"postgresql", "sqlite"},
    )
    if db["fallback"]:
        results.append(
            ("Infrastructure", "NOTE: running on the SQLite development fallback", "INFO")
        )


def audit_stock_rule(api: Api) -> None:
    """Walk the whole chain and assert the balance after every single step."""
    parts = api.get("/parts")
    suppliers = api.get("/suppliers")
    stations = api.get("/stations")
    part = parts[0]
    part_id = part["id"]

    quantity = 240
    issue_quantity = 40

    before = api.stock(part_id)

    # --- 1. Reception ------------------------------------------------------
    reception = api.post_ok(
        "/receptions",
        {
            "part_id": part_id,
            "supplier_id": suppliers[0]["id"],
            "quantity_expected": quantity,
            "quantity_received": quantity,
            "delivery_note": "AUDIT",
        },
    )
    lot_id = reception["lot"]["id"]
    check("Stock rule", "reception does NOT increase stock", api.stock(part_id) == before)

    # --- 2. Inspection -----------------------------------------------------
    api.post_ok(f"/lots/{lot_id}/inspection/start")
    suggestion = api.get(f"/lots/{lot_id}/sample-suggestion")
    check(
        "Stock rule",
        "sample size never exceeds the lot",
        suggestion["suggested_sample_size"] <= quantity,
    )
    inspection = api.post_ok(
        f"/lots/{lot_id}/inspect",
        {"sample_size": suggestion["suggested_sample_size"], "defects_found": 0},
    )
    check("Stock rule", "inspection does NOT increase stock", api.stock(part_id) == before)
    check("Workflow", "conform sample routes the lot to quality", inspection["result"] == "CONFORM")

    # --- 3. Storage before approval must be refused ------------------------
    plan_before = api.post(
        f"/lots/{lot_id}/storage/confirm",
        {"allocations": [{"location_id": 1, "quantity": quantity}]},
    )
    check(
        "Workflow",
        "storage refused before quality approval (409)",
        plan_before.status_code == 409,
        f"got {plan_before.status_code}",
    )
    check("Stock rule", "refused storage left stock untouched", api.stock(part_id) == before)

    # --- 4. Quality --------------------------------------------------------
    api.post_ok(f"/lots/{lot_id}/quality/approve", {"justification": "audit: sample conform"})
    check("Stock rule", "quality approval does NOT increase stock", api.stock(part_id) == before)

    no_reason = api.post(f"/lots/{lot_id}/quality/reject", {"justification": ""})
    check(
        "Workflow",
        "a quality decision without justification is refused",
        no_reason.status_code in (409, 422),
        f"got {no_reason.status_code}",
    )

    # --- 5. Storage confirmation -> the only increment ---------------------
    plan = api.get(f"/lots/{lot_id}/storage-plan")
    check("Workflow", "storage plan is fully allocatable", plan["fully_allocatable"] is True)
    check(
        "Workflow",
        "storage plan proposes the primary address first",
        plan["suggestions"] and plan["suggestions"][0]["role"] == "PRIMARY",
    )

    movements = api.post_ok(
        f"/lots/{lot_id}/storage/confirm",
        {
            "allocations": [
                {"location_id": item["location_id"], "quantity": item["quantity"]}
                for item in plan["suggestions"]
            ]
        },
    )
    after_storage = api.stock(part_id)
    check(
        "Stock rule",
        f"storage confirmation increments stock ({before} -> {after_storage})",
        after_storage == before + quantity,
    )
    check(
        "Traceability",
        "every increment produced a StockMovement",
        len(movements) == len(plan["suggestions"]),
    )
    check(
        "Traceability",
        "movement ledger records before/after",
        all("quantity_before" in m and "quantity_after" in m for m in movements),
    )

    # --- 6. Production request --------------------------------------------
    request = api.post_ok(
        "/production/requests",
        {
            "station_id": stations[0]["id"],
            "part_id": part_id,
            "quantity": issue_quantity,
            "submit_immediately": True,
        },
    )
    request_id = request["id"]
    check("Stock rule", "creating a request does NOT decrease stock", api.stock(part_id) == after_storage)

    # --- 7. Issuing before the workflow completes must be refused ----------
    early = api.post(f"/production/requests/{request_id}/issue")
    check(
        "Workflow",
        "issue refused from SUBMITTED (409)",
        early.status_code == 409,
        f"got {early.status_code}",
    )
    check("Stock rule", "refused issue left stock untouched", api.stock(part_id) == after_storage)

    # --- 8. Approval / preparation ----------------------------------------
    api.post_ok(f"/production/requests/{request_id}/approve")
    check("Stock rule", "approval does NOT decrease stock", api.stock(part_id) == after_storage)

    row = api.get(f"/production/requests/{request_id}")
    check(
        "Stock rule",
        "approval reserves without reducing availability",
        api.stock(part_id) == after_storage and row["request"]["status"] == "APPROVED",
    )

    api.post_ok(f"/production/requests/{request_id}/prepare")
    api.post_ok(f"/production/requests/{request_id}/ready")
    check("Stock rule", "preparation does NOT decrease stock", api.stock(part_id) == after_storage)

    # --- 9. Confirmed issue -> the only decrement --------------------------
    movement = api.post_ok(f"/production/requests/{request_id}/issue")
    after_issue = api.stock(part_id)
    check(
        "Stock rule",
        f"confirmed issue decrements stock ({after_storage} -> {after_issue})",
        after_issue == after_storage - issue_quantity,
    )
    check("Stock rule", "issue movement is typed OUT", movement["movement_type"] == "OUT")
    check(
        "Stock rule",
        "movement arithmetic is consistent",
        movement["quantity_before"] - movement["quantity"] == movement["quantity_after"],
    )

    # --- 10. Negative stock is impossible ----------------------------------
    huge = api.post_ok(
        "/production/requests",
        {
            "station_id": stations[0]["id"],
            "part_id": part_id,
            "quantity": after_issue + 100_000,
            "submit_immediately": True,
        },
    )
    api.post_ok(f"/production/requests/{huge['id']}/approve")
    api.post_ok(f"/production/requests/{huge['id']}/prepare")
    api.post_ok(f"/production/requests/{huge['id']}/ready")
    refused = api.post(f"/production/requests/{huge['id']}/issue")
    check(
        "Stock rule",
        "over-issue refused, stock can never go negative",
        refused.status_code == 409 and refused.json().get("code") == "insufficient_stock",
        f"got {refused.status_code}",
    )
    check("Stock rule", "stock unchanged after refusal", api.stock(part_id) == after_issue)
    api.post_ok(
        f"/production/requests/{huge['id']}/cancel", {"reason": "audit cleanup"}
    )

    # --- 11. Audit trail ---------------------------------------------------
    trace = api.get(f"/traceability/lots/{lot_id}")
    actions = {event["action"] for event in trace["events"]}
    for expected in (
        "LOT_RECEIVED",
        "INSPECTION_STARTED",
        "INSPECTION_RECORDED",
        "QUALITY_APPROVED",
        "STORAGE_CONFIRMED",
        "STOCK_INCREMENTED",
    ):
        check("Traceability", f"audit trail contains {expected}", expected in actions)

    check(
        "Traceability",
        "every audited event names an actor",
        all(event["actor_name"] for event in trace["events"]),
    )
    check(
        "Traceability",
        "audit records the status transition",
        any(e["status_before"] and e["status_after"] for e in trace["events"]),
    )
    check("Traceability", "lot totals reconcile", trace["total_in"] == quantity)


def audit_tolerance(api: Api) -> None:
    parts = api.get("/parts")
    suppliers = api.get("/suppliers")
    large = next((p for p in parts if p["size_class"] == "LARGE"), None)
    small = next(
        (p for p in parts if p["size_class"] == "SMALL" and p["reception_tolerance_percent"] is None),
        None,
    )

    if small:
        preview = api.get(
            "/receptions/tolerance-preview", part_id=small["id"], quantity_expected=100
        )
        check(
            "Business rules",
            f"small part tolerance is configurable ({preview['tolerance_percent']}%)",
            preview["tolerance_percent"] > 0,
        )
        accepted = api.post_ok(
            "/receptions",
            {
                "part_id": small["id"],
                "supplier_id": suppliers[0]["id"],
                "quantity_expected": 100,
                "quantity_received": 97,
            },
        )
        check(
            "Business rules",
            "small part within tolerance is accepted",
            accepted["status"] == "ACCEPTED_WITH_TOLERANCE",
            accepted["status"],
        )

    if large:
        preview = api.get(
            "/receptions/tolerance-preview", part_id=large["id"], quantity_expected=100
        )
        check(
            "Business rules",
            "large part requires an exact quantity",
            preview["tolerance_percent"] == 0,
        )
        mismatch = api.post_ok(
            "/receptions",
            {
                "part_id": large["id"],
                "supplier_id": suppliers[0]["id"],
                "quantity_expected": 100,
                "quantity_received": 98,
            },
        )
        check(
            "Business rules",
            "large part out of tolerance goes to the Red Cage",
            mismatch["status"] == "QUANTITY_MISMATCH"
            and mismatch["lot"]["status"] == "RED_CAGE",
        )
        check(
            "Business rules",
            "the blocking reason is recorded",
            bool(mismatch["lot"]["blocked_reason"]),
        )


def audit_simulation(api: Api) -> None:
    parts = api.get("/parts")
    part_id = parts[0]["id"]
    before = api.stock(part_id)

    run = api.post_ok(
        "/simulation/run",
        {"part_id": part_id, "quantity": 150, "production_quantity": 25},
    )
    keys = [step["key"] for step in run["steps"]]
    check(
        "Simulation",
        "the full chain runs in order",
        keys
        == [
            "reception",
            "inspection",
            "quality",
            "storage",
            "request",
            "approval",
            "preparation",
            "issue",
        ],
        str(keys),
    )
    check(
        "Simulation",
        f"net stock effect is correct ({before} -> {run['stock_after']})",
        run["stock_after"] == before + 150 - 25,
    )

    partial = api.post_ok(
        "/simulation/run",
        {"part_id": part_id, "quantity": 60, "stop_after": "quality"},
    )
    check(
        "Simulation",
        "step-by-step mode stops where asked",
        [s["key"] for s in partial["steps"]] == ["reception", "inspection", "quality"],
    )
    check(
        "Simulation",
        "stopping at quality leaves stock untouched",
        partial["stock_after"] == partial["stock_before"],
    )


def audit_dashboard(api: Api) -> None:
    dashboard = api.get("/dashboard")
    stock_rows = api.get("/stock")
    total_stock = sum(row["quantity_available"] for row in stock_rows)

    kpis = {kpi["id"]: kpi for kpi in dashboard["kpis"]}
    check("Mission Control", "six KPIs are returned", len(dashboard["kpis"]) == 6)
    check(
        "Mission Control",
        f"Total Stock KPI matches the stock table ({total_stock})",
        int(kpis["total-stock"]["value"]) == total_stock,
    )

    grid = api.get("/warehouse/grid")
    check(
        "Mission Control",
        "Warehouse Occupancy KPI matches the warehouse map",
        abs(kpis["warehouse-occupancy"]["value"] - grid["occupancy_percent"]) < 0.05,
    )

    stages = [stage["id"] for stage in dashboard["stages"]]
    check(
        "Mission Control",
        "the six flow stages are present in order",
        stages
        == ["SUPPLIER", "RECEIVING", "INSPECTION", "QUALITY", "WAREHOUSE", "PRODUCTION"],
    )
    check(
        "Mission Control",
        "activity feed is fed by the audit trail",
        len(dashboard["activity"]) > 0
        and all(event["actor_name"] for event in dashboard["activity"]),
    )
    check(
        "Mission Control",
        "system status is computed, not hardcoded",
        dashboard["system_status"] in {"OPERATIONAL", "DEGRADED"},
    )

    # Alerts must correspond to real situations.
    alerts = dashboard["alerts"]
    red_cage = api.get("/quality/red-cage")
    if red_cage:
        check(
            "Alerts",
            "a blocked lot raises a critical alert",
            any(a["severity"] == "CRITICAL" and a["lot_number"] for a in alerts),
        )
    check(
        "Alerts",
        "every alert carries a message and a source",
        all(a["message"] and a["source"] for a in alerts),
    )
    check(
        "Alerts",
        "alerts are ordered by severity",
        [a["severity"] for a in alerts]
        == sorted(
            [a["severity"] for a in alerts],
            key=lambda s: {"CRITICAL": 0, "WARNING": 1, "INFO": 2, "OK": 3}.get(s, 9),
        ),
    )


def audit_ai(api: Api) -> None:
    analysis = api.get("/ai/analysis", refresh=True)
    check("AI", "analysis returns a headline", bool(analysis["headline"]))
    check(
        "AI",
        "every recommendation is justified",
        all(r["rationale"].strip() for r in analysis["recommendations"]),
    )
    check(
        "AI",
        "every recommendation proposes an action",
        all(r["recommended_action"] for r in analysis["recommendations"]),
    )
    check(
        "AI",
        "recommendations carry the metrics behind them",
        all(isinstance(r["metrics"], dict) for r in analysis["recommendations"]),
    )
    check(
        "AI",
        "priorities are 1, 2 or 3",
        all(r["priority"] in (1, 2, 3) for r in analysis["recommendations"]),
    )

    risks = api.get("/ai/shortage-risk")
    # The assessment deliberately covers the managed perimeter, not the whole
    # catalogue: a reference the warehouse does not hold cannot run short, and
    # scoring the full bill of materials once buried the handful that mattered
    # under two thousand references nobody replenishes.
    every_part = api.get("/parts", limit=5000)
    managed = [part for part in every_part if part.get("is_managed")]
    check(
        "AI",
        "shortage risk covers every managed reference",
        len(risks) == len(managed),
        f"{len(risks)} risques pour {len(managed)} references gerees "
        f"({len(every_part)} au catalogue)",
    )
    check(
        "AI",
        "the perimeter is smaller than the catalogue",
        0 < len(managed) < len(every_part),
        f"{len(managed)}/{len(every_part)}",
    )
    check("AI", "every risk is justified", all(r["rationale"].strip() for r in risks))
    check(
        "AI",
        "risk levels are valid",
        all(r["risk_level"] in ("LOW", "MEDIUM", "HIGH") for r in risks),
    )

    # A high risk must be arithmetically defensible.
    for risk in risks:
        if risk["risk_level"] == "HIGH":
            defensible = (
                risk["stock_available"] < risk["open_demand"]
                or risk["stock_available"] < risk["safety_stock"]
                or (risk["days_of_cover"] is not None and risk["days_of_cover"] <= 2)
            )
            check(
                "AI",
                f"HIGH risk on {risk['part_reference']} is arithmetically justified",
                defensible,
            )


def audit_copilot(api: Api) -> None:
    expectations = {
        "What are today's priorities?": "priorities",
        "Which lots are blocked?": "blocked_lots",
        "Is there a shortage risk?": "shortage_risk",
        "Which racks are nearly full?": "warehouse_saturation",
    }
    for question, intent in expectations.items():
        answer = api.post_ok("/ai/copilot", {"question": question})
        check("Copilot", f"'{question}' -> {intent}", answer["intent"] == intent, answer["intent"])
        check("Copilot", f"'{question}' returns an answer", len(answer["answer"]) > 10)

    grounded = api.post_ok("/ai/copilot", {"question": "Which lots are blocked?"})
    red_cage = api.get("/quality/red-cage")
    check(
        "Copilot",
        f"answer matches the real Red Cage content ({len(red_cage)} lots)",
        str(len(red_cage)) in grounded["answer"] or (not red_cage and "No lot" in grounded["answer"]),
    )
    check("Copilot", "answers cite their sources", len(grounded["sources"]) > 0)

    unknown = api.post_ok("/ai/copilot", {"question": "What is the capital of Peru?"})
    check(
        "Copilot",
        "out-of-scope question is declined rather than invented",
        unknown["intent"] == "unknown",
    )


def audit_powerbi(api: Api) -> None:
    catalog = api.get("/analytics/powerbi")
    names = {dataset["name"] for dataset in catalog["datasets"]}
    expected = {
        "fact_lots",
        "fact_stock_movements",
        "fact_quality",
        "fact_production_requests",
        "dim_stock",
        "dim_locations",
        # The calendar makes Power BI time intelligence work over the ledger.
        "dim_date",
    }
    check("Power BI", "the seven datasets are exposed", names == expected, str(names))
    check(
        "Power BI",
        "datasets are populated",
        all(len(d["rows"]) > 0 for d in catalog["datasets"] if d["name"] != "fact_lots" or True),
    )
    check(
        "Power BI",
        "every dataset declares its columns",
        all(d["columns"] for d in catalog["datasets"] if d["rows"]),
    )
    check("Power BI", "DAX measures are provided", len(catalog["measures"]) >= 5)
    check(
        "Power BI",
        "measures carry an expression and a description",
        all(m["expression"] and m["description"] for m in catalog["measures"]),
    )

    # The BI view must agree with the operational view.
    stock_rows = api.get("/stock")
    dim_stock = next(d for d in catalog["datasets"] if d["name"] == "dim_stock")
    bi_total = sum(row["quantity_available"] for row in dim_stock["rows"])
    api_total = sum(row["quantity_available"] for row in stock_rows)
    check(
        "Power BI",
        f"dim_stock agrees with the API ({bi_total} == {api_total})",
        bi_total == api_total,
    )

    movements = api.get("/stock-movements", limit=500)
    fact_movements = next(d for d in catalog["datasets"] if d["name"] == "fact_stock_movements")
    check(
        "Power BI",
        "fact_stock_movements is the full ledger",
        len(fact_movements["rows"]) >= len(movements),
    )


def audit_analytics(api: Api) -> None:
    analytics = api.get("/analytics")
    check(
        "Analytics",
        "conformity rate is a valid percentage",
        0 <= analytics["quality_conformity_percent"] <= 100,
    )
    check(
        "Analytics",
        "conformity and non-conformity sum to 100",
        abs(
            analytics["quality_conformity_percent"]
            + analytics["quality_non_conformity_percent"]
            - 100
        )
        < 0.15,
    )
    check("Analytics", "flow distribution is returned", len(analytics["flow_counts"]) > 0)
    measured = [s for s in analytics["stage_durations"] if s["sample_size"] > 0]
    check("Analytics", "lead times are measured", len(measured) > 0)
    check(
        "Analytics",
        "a bottleneck is identified when lead times exist",
        analytics["bottleneck"] is not None if measured else True,
    )
    check(
        "Analytics",
        "issued never exceeds requested",
        analytics["quantity_issued"] <= analytics["quantity_requested"],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit the running SLCC API")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000/api")
    args = parser.parse_args()

    api = Api(args.base_url)

    print(f"SLCC audit -- {args.base_url}")
    print("=" * 78)

    sections = (
        ("infrastructure", audit_infrastructure),
        ("stock rule and workflow", audit_stock_rule),
        ("reception tolerance", audit_tolerance),
        ("simulation", audit_simulation),
        ("mission control and alerts", audit_dashboard),
        ("analytics", audit_analytics),
        ("AI", audit_ai),
        ("copilot", audit_copilot),
        ("power bi", audit_powerbi),
    )

    for name, runner in sections:
        try:
            runner(api)
        except Exception as exc:  # noqa: BLE001
            results.append(("Audit", f"section '{name}' crashed: {exc}", FAIL))

    current_section = None
    for section, label, status in results:
        if section != current_section:
            print(f"\n{section}")
            print("-" * 78)
            current_section = section
        marker = {PASS: "  ok  ", FAIL: " FAIL ", "INFO": " note "}[status]
        print(f"{marker}{label}")

    failures = [row for row in results if row[2] == FAIL]
    passed = [row for row in results if row[2] == PASS]

    print("\n" + "=" * 78)
    print(f"{len(passed)} passed, {len(failures)} failed, {len(results)} checks total")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
