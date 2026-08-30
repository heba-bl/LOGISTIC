"""API-level tests, including the full demonstration scenario over HTTP."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_session
from app.main import app


@pytest.fixture()
def client(db, world):
    """TestClient bound to the isolated test session."""
    app.dependency_overrides[get_session] = lambda: db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_health_contract_is_unchanged(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "smart-logistics-api"}


def test_dashboard_returns_live_figures(client, world):
    response = client.get("/api/dashboard")
    assert response.status_code == 200

    payload = response.json()
    assert {"kpis", "stages", "alerts", "activity", "system_status"} <= payload.keys()
    assert len(payload["kpis"]) == 6
    assert len(payload["stages"]) == 6
    assert [stage["id"] for stage in payload["stages"]] == [
        "SUPPLIER",
        "RECEIVING",
        "INSPECTION",
        "QUALITY",
        "WAREHOUSE",
        "PRODUCTION",
    ]


def test_tolerance_preview_explains_the_rule(client, world):
    response = client.get(
        "/api/receptions/tolerance-preview",
        params={"part_id": world["small"].id, "quantity_expected": 200},
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload["tolerance_percent"] == 5.0
    assert payload["minimum_accepted"] == 190
    assert payload["maximum_accepted"] == 210


def test_full_flow_over_http(client, world):
    """Reception -> inspection -> quality -> storage -> request -> issue."""
    part_id = world["small"].id

    # 1. Reception - no stock yet.
    reception = client.post(
        "/api/receptions",
        json={
            "part_id": part_id,
            "supplier_id": world["supplier"].id,
            "quantity_expected": 100,
            "quantity_received": 100,
            "actor_id": world["user"].id,
        },
    )
    assert reception.status_code == 201
    lot_id = reception.json()["lot"]["id"]
    assert client.get(f"/api/stock/{part_id}").json()["quantity_available"] == 0

    # 2. Inspection.
    assert client.post(f"/api/lots/{lot_id}/inspection/start").status_code == 200
    inspect = client.post(
        f"/api/lots/{lot_id}/inspect",
        json={"sample_size": 10, "defects_found": 0, "actor_id": world["user"].id},
    )
    assert inspect.status_code == 201
    assert inspect.json()["result"] == "CONFORM"
    assert client.get(f"/api/stock/{part_id}").json()["quantity_available"] == 0

    # 3. Quality approval - still no stock.
    approve = client.post(
        f"/api/lots/{lot_id}/quality/approve",
        json={"justification": "sample conform", "actor_id": world["user"].id},
    )
    assert approve.status_code == 200
    assert client.get(f"/api/stock/{part_id}").json()["quantity_available"] == 0

    # 4. Storage confirmation - stock appears.
    plan = client.get(f"/api/lots/{lot_id}/storage-plan").json()
    assert plan["fully_allocatable"] is True

    storage = client.post(
        f"/api/lots/{lot_id}/storage/confirm",
        json={
            "allocations": [
                {"location_id": item["location_id"], "quantity": item["quantity"]}
                for item in plan["suggestions"]
            ],
            "actor_id": world["user"].id,
        },
    )
    assert storage.status_code == 201
    assert client.get(f"/api/stock/{part_id}").json()["quantity_available"] == 100

    # 5. Production request - no decrement.
    request = client.post(
        "/api/production/requests",
        json={
            "station_id": world["station"].id,
            "part_id": part_id,
            "quantity": 30,
            "actor_id": world["user"].id,
            "submit_immediately": True,
        },
    )
    assert request.status_code == 201
    request_id = request.json()["id"]
    assert client.get(f"/api/stock/{part_id}").json()["quantity_available"] == 100

    # 6. Approve, prepare, ready - still no decrement.
    for step in ("approve", "prepare", "ready"):
        response = client.post(f"/api/production/requests/{request_id}/{step}", json={})
        assert response.status_code == 200, f"{step}: {response.text}"
    assert client.get(f"/api/stock/{part_id}").json()["quantity_available"] == 100

    # 7. Issue - the only decrement.
    issue = client.post(f"/api/production/requests/{request_id}/issue", json={})
    assert issue.status_code == 200
    assert issue.json()["movement_type"] == "OUT"
    assert client.get(f"/api/stock/{part_id}").json()["quantity_available"] == 70

    # 8. Traceability records the whole journey.
    trace = client.get(f"/api/traceability/lots/{lot_id}").json()
    actions = [event["action"] for event in trace["events"]]
    for expected in (
        "LOT_RECEIVED",
        "INSPECTION_STARTED",
        "INSPECTION_RECORDED",
        "QUALITY_APPROVED",
        "STORAGE_CONFIRMED",
        "STOCK_INCREMENTED",
    ):
        assert expected in actions, f"{expected} missing from the audit trail"
    assert trace["total_in"] == 100


def test_storage_without_approval_is_refused_with_a_clear_error(client, world):
    reception = client.post(
        "/api/receptions",
        json={
            "part_id": world["small"].id,
            "supplier_id": world["supplier"].id,
            "quantity_expected": 50,
            "quantity_received": 50,
        },
    )
    lot_id = reception.json()["lot"]["id"]

    response = client.post(
        f"/api/lots/{lot_id}/storage/confirm",
        json={"allocations": [{"location_id": world["primary"].id, "quantity": 50}]},
    )
    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "workflow_error"
    assert "quality approval" in body["message"].lower()


def test_simulation_runs_the_whole_chain(client, world):
    response = client.post(
        "/api/simulation/run",
        json={"part_id": world["small"].id, "quantity": 120, "production_quantity": 20},
    )
    assert response.status_code == 200

    payload = response.json()
    keys = [step["key"] for step in payload["steps"]]
    assert keys == [
        "reception",
        "inspection",
        "quality",
        "storage",
        "request",
        "approval",
        "preparation",
        "issue",
    ]
    assert payload["stock_after"] == payload["stock_before"] + 100


def test_simulation_can_stop_at_a_given_step(client, world):
    response = client.post(
        "/api/simulation/run",
        json={"part_id": world["small"].id, "quantity": 60, "stop_after": "quality"},
    )
    payload = response.json()

    assert [step["key"] for step in payload["steps"]] == [
        "reception",
        "inspection",
        "quality",
    ]
    # Quality approval alone must never create stock.
    assert payload["stock_after"] == payload["stock_before"]


def test_ai_analysis_always_explains_itself(client, world):
    client.post(
        "/api/simulation/run",
        json={"part_id": world["small"].id, "quantity": 60, "production_quantity": 10},
    )
    response = client.get("/api/ai/analysis")
    assert response.status_code == 200

    payload = response.json()
    assert payload["headline"]
    for recommendation in payload["recommendations"]:
        assert recommendation["rationale"], "a recommendation must always be justified"
    for risk in payload["shortage_risks"]:
        assert risk["rationale"]


def test_copilot_answers_from_the_data(client, world):
    client.post(
        "/api/simulation/run",
        json={"part_id": world["small"].id, "quantity": 200, "production_quantity": 20},
    )

    response = client.post("/api/ai/copilot", json={"question": "Which lots are blocked?"})
    assert response.status_code == 200
    assert response.json()["intent"] == "blocked_lots"

    stock = client.post("/api/ai/copilot", json={"question": "What is the SM-100 stock?"})
    assert stock.json()["intent"] == "stock_level"
    assert "180" in stock.json()["answer"] or "SM-100" in stock.json()["answer"]


def test_analytics_and_powerbi_datasets_are_available(client, world):
    client.post("/api/simulation/run", json={"part_id": world["small"].id, "quantity": 80})

    analytics = client.get("/api/analytics")
    assert analytics.status_code == 200
    assert analytics.json()["quality_conformity_percent"] >= 0

    powerbi = client.get("/api/analytics/powerbi")
    assert powerbi.status_code == 200
    names = {dataset["name"] for dataset in powerbi.json()["datasets"]}
    assert {
        "fact_lots",
        "fact_stock_movements",
        "fact_quality",
        "fact_production_requests",
        "dim_stock",
        "dim_locations",
        # The calendar the time-intelligence measures are built on.
        "dim_date",
    } == names


def test_warehouse_grid_reflects_real_occupancy(client, world):
    client.post("/api/simulation/run", json={"part_id": world["small"].id, "quantity": 100})

    grid = client.get("/api/warehouse/grid").json()
    assert grid["total_occupied"] > 0
    assert grid["zones"]

    occupied = [item for item in grid["locations"] if item["occupied"] > 0]
    assert occupied, "storage must be visible on the warehouse map"

    detail = client.get(f"/api/warehouse/locations/{occupied[0]['id']}").json()
    assert detail["references"]


def test_settings_are_editable_and_audited(client, world):
    response = client.put(
        "/api/settings/reception.tolerance_percent_small", json={"value": "7.5"}
    )
    assert response.status_code == 200
    assert response.json()["value"] == "7.5"

    preview = client.get(
        "/api/receptions/tolerance-preview",
        params={"part_id": world["small"].id, "quantity_expected": 100},
    ).json()
    assert preview["tolerance_percent"] == 7.5


# --------------------------------------------------- Maker-Checker over HTTP
def _operator(db, *, matricule, username, role_name, service):
    from sqlalchemy import select

    from app.models.organization import Role, User

    role = db.execute(select(Role).where(Role.name == role_name)).scalar_one_or_none()
    if role is None:
        role = Role(name=role_name, label=role_name.value.replace("_", " ").title())
        db.add(role)
        db.flush()
    user = User(
        employee_number=matricule,
        username=username,
        full_name=username.title(),
        role_id=role.id,
        service=service,
    )
    db.add(user)
    db.flush()
    return user


def test_import_workflow_over_http(client, db, world):
    """Upload as maker, refuse self-validation, approve as a habilitated checker."""
    from app.models.enums import RoleName

    maker = _operator(
        db,
        matricule="OP-9001",
        username="maker",
        role_name=RoleName.RECEPTIONIST,
        service="Reception",
    )
    checker = _operator(
        db,
        matricule="RM-9002",
        username="checker",
        role_name=RoleName.RECEPTION_MANAGER,
        service="Reception",
    )

    csv = (
        "part_reference,supplier_code,quantity_expected,quantity_received,delivery_note,notes\n"
        f"{world['small'].reference},{world['supplier'].code},120,120,BL-HTTP,\n"
    ).encode()

    lots_before = len(client.get("/api/lots").json())

    # 1. Upload - nothing enters the system.
    upload = client.post(
        "/api/imports",
        data={"import_type": "RECEPTION", "maker_id": str(maker.id)},
        files={"file": ("receptions.csv", csv, "text/csv")},
    )
    assert upload.status_code == 201, upload.text
    batch = upload.json()
    assert batch["status"] == "PENDING_REVIEW"
    assert batch["maker_reference"] == "OP-9001"
    assert batch["source_hash"]
    assert len(client.get("/api/lots").json()) == lots_before

    import_id = batch["id"]

    # 2. The maker cannot validate their own entry.
    refused = client.post(
        f"/api/imports/{import_id}/approve", json={"checker_id": maker.id}
    )
    assert refused.status_code == 409
    assert refused.json()["code"] == "workflow_error"
    assert len(client.get("/api/lots").json()) == lots_before

    # 3. The maker is never offered as a checker.
    checkers = client.get(f"/api/imports/{import_id}/checkers").json()
    assert "OP-9001" not in {item["employee_number"] for item in checkers}
    assert "RM-9002" in {item["employee_number"] for item in checkers}

    # 4. A habilitated checker approves: only now is the data applied.
    approved = client.post(
        f"/api/imports/{import_id}/approve",
        json={"checker_id": checker.id, "comment": "Checked against the delivery note"},
    )
    assert approved.status_code == 200, approved.text
    body = approved.json()
    assert body["status"] == "APPROVED"
    assert body["checker_reference"] == "RM-9002"
    assert body["applied_row_count"] == 1
    assert len(client.get("/api/lots").json()) == lots_before + 1


def test_import_rejection_over_http(client, db, world):
    from app.models.enums import RoleName

    maker = _operator(
        db,
        matricule="OP-9003",
        username="maker3",
        role_name=RoleName.RECEPTIONIST,
        service="Reception",
    )
    checker = _operator(
        db,
        matricule="RM-9004",
        username="checker4",
        role_name=RoleName.RECEPTION_MANAGER,
        service="Reception",
    )

    csv = (
        "part_reference,supplier_code,quantity_expected,quantity_received,delivery_note,notes\n"
        f"{world['small'].reference},{world['supplier'].code},90,90,BL-REJ,\n"
    ).encode()

    lots_before = len(client.get("/api/lots").json())
    batch = client.post(
        "/api/imports",
        data={"import_type": "RECEPTION", "maker_id": str(maker.id)},
        files={"file": ("r.csv", csv, "text/csv")},
    ).json()

    # A rejection without a reason is refused by the schema.
    empty = client.post(
        f"/api/imports/{batch['id']}/reject",
        json={"checker_id": checker.id, "comment": ""},
    )
    assert empty.status_code == 422

    rejected = client.post(
        f"/api/imports/{batch['id']}/reject",
        json={"checker_id": checker.id, "comment": "Physical count does not match"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "REJECTED"
    assert rejected.json()["applied_row_count"] == 0
    assert len(client.get("/api/lots").json()) == lots_before


def test_import_template_is_downloadable(client):
    response = client.get("/api/imports/template", params={"import_type": "RECEPTION"})
    assert response.status_code == 200
    assert "spreadsheetml" in response.headers["content-type"]
    assert response.content[:2] == b"PK"  # xlsx is a zip archive


def test_import_types_expose_the_habilitation_matrix(client):
    types = client.get("/api/imports/types").json()
    assert {item["value"] for item in types} == {
        "RECEPTION",
        "INSPECTION",
        "PRODUCTION_REQUEST",
    }
    inspection = next(item for item in types if item["value"] == "INSPECTION")
    # An inspector may enter, but never validate, an inspection.
    assert "QUALITY_INSPECTOR" in inspection["maker_roles"]
    assert "QUALITY_INSPECTOR" not in inspection["checker_roles"]
    assert "QUALITY_MANAGER" in inspection["checker_roles"]
