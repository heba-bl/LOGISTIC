"""Mission Control payload and the alert shortlist."""

from __future__ import annotations

from app.services import dashboard_service


def test_dashboard_payload_is_complete(db, world):
    payload = dashboard_service.build_dashboard(db)

    assert payload["system_status"] in {"OPERATIONAL", "DEGRADED"}
    assert len(payload["kpis"]) > 0
    assert payload["stages"], "les six etapes du flux"
    for kpi in payload["kpis"]:
        assert kpi["label"] and kpi["severity"]


def test_system_status_follows_the_critical_alerts(db, world):
    """The banner is computed, never hardcoded."""
    payload = dashboard_service.build_dashboard(db)
    critical = [alert for alert in payload["alerts"] if alert["severity"] == "CRITICAL"]
    assert payload["system_status"] == ("DEGRADED" if critical else "OPERATIONAL")


def test_every_alert_names_its_source(db, world):
    for alert in dashboard_service.build_alerts(db):
        assert alert["message"], alert
        assert alert["source"], alert
        assert alert["kind"], "chaque alerte porte son type, pour le classement"


def test_stages_report_real_quantities(db, world):
    stages = dashboard_service.build_stages(db)
    identifiers = [stage["id"] for stage in stages]
    assert identifiers == [
        "SUPPLIER",
        "RECEIVING",
        "INSPECTION",
        "QUALITY",
        "WAREHOUSE",
        "PRODUCTION",
    ]
    for stage in stages:
        assert stage["quantity"] >= 0
        assert stage["lot_count"] >= 0


# ------------------------------------------------------------ alert shortlist
def _alert(identifier: str, kind: str, severity: str, title: str) -> dict:
    from datetime import datetime, timezone

    return {
        "id": identifier,
        "kind": kind,
        "severity": severity,
        "title": title,
        "message": "m",
        "source": "s",
        "timestamp": datetime.now(timezone.utc),
        "lot_number": None,
        "part_reference": None,
        "location_code": None,
    }


def test_alert_shortlist_never_shows_one_kind_only():
    """Twenty saturated racks must not hide the single blocked lot."""
    from app.services.dashboard_service import top_alerts

    alerts = [
        _alert(f"loc-{index}", "LOCATION_SATURATED", "CRITICAL", "Location saturated")
        for index in range(20)
    ]
    alerts.append(_alert("redcage-1", "RED_CAGE", "CRITICAL", "Lot blocked in Red Cage"))

    shortlist = top_alerts(alerts, limit=8)

    assert len(shortlist) == 8
    assert any(item["kind"] == "RED_CAGE" for item in shortlist)
    kinds = {item["kind"] for item in shortlist}
    assert len(kinds) > 1


def test_alert_shortlist_counts_what_it_hides():
    """Truncation is stated, never silent."""
    from app.services.dashboard_service import top_alerts

    alerts = [
        _alert(f"loc-{index}", "LOCATION_SATURATED", "CRITICAL", "Location saturated")
        for index in range(30)
    ]

    shortlist = top_alerts(alerts, limit=8)
    summary = [item for item in shortlist if item["kind"] == "MORE"]

    assert len(summary) == 1
    assert "23" in summary[0]["title"], summary[0]["title"]
    assert "Location saturated" in summary[0]["message"]


def test_short_alert_list_is_returned_untouched():
    from app.services.dashboard_service import top_alerts

    alerts = [_alert("redcage-1", "RED_CAGE", "CRITICAL", "Lot blocked in Red Cage")]
    assert top_alerts(alerts, limit=8) == alerts
