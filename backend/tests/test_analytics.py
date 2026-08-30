"""Analytical indicators and the Power BI hand-off."""

from __future__ import annotations

from app.services import analytics_service


def test_analytics_payload_covers_every_axis(db, world):
    payload = analytics_service.build_analytics(db)

    for field in (
        "stock_by_category",
        "stock_by_part",
        "flow_counts",
        "stage_durations",
        "quality_conformity_percent",
        "consumption_by_part",
    ):
        assert field in payload, field

    assert 0 <= payload["quality_conformity_percent"] <= 100
    assert payload["quality_non_conformity_percent"] == round(
        100 - payload["quality_conformity_percent"], 1
    )


def test_only_one_stage_is_the_bottleneck(db, world):
    """Two bottlenecks is a contradiction, not a finding."""
    durations = analytics_service.stage_durations(db)
    flagged = [row for row in durations if row["is_bottleneck"]]
    assert len(flagged) <= 1

    measured = [row for row in durations if row["sample_size"] > 0]
    if measured:
        assert len(flagged) == 1
        assert flagged[0]["average_hours"] == max(row["average_hours"] for row in measured)


def test_a_stage_without_measurements_is_not_invented(db, world):
    for row in analytics_service.stage_durations(db):
        if row["sample_size"] == 0:
            assert row["average_hours"] == 0.0
            assert not row["is_bottleneck"]


# --------------------------------------------------- power bi model integrity
def test_every_dax_measure_references_an_existing_column(db, world):
    """A measure pointing at a column that is not shipped fails in Power BI.

    The model is a contract between two products: if the API stops exposing a
    column, the report breaks silently in someone else's tool. This keeps the
    two in step.
    """
    import re

    from app.services import analytics_service

    catalog = analytics_service.powerbi_datasets(db)
    columns = {dataset["name"]: set(dataset["columns"]) for dataset in catalog["datasets"]}

    problems: list[str] = []
    for measure in catalog["measures"]:
        for table, column in re.findall(r"(\w+)\[(\w+)\]", measure["expression"]):
            if table not in columns:
                # A DAX variable, not a table.
                continue
            if column not in columns[table]:
                problems.append(f"{measure['name']}: {table}[{column}]")

    assert not problems, f"colonnes absentes du modele: {problems}"


def test_powerbi_datasets_declare_their_columns(db, world):
    from app.services import analytics_service

    catalog = analytics_service.powerbi_datasets(db)
    names = {dataset["name"] for dataset in catalog["datasets"]}
    assert {"fact_lots", "fact_production_requests", "dim_stock", "dim_date"} <= names

    for dataset in catalog["datasets"]:
        if dataset["rows"]:
            assert set(dataset["columns"]) == set(dataset["rows"][0]), dataset["name"]


def test_powerbi_theme_uses_the_application_palette():
    """One palette across the app and the report, or they read as two products."""
    from app.services import analytics_service

    theme = analytics_service.powerbi_theme()
    assert theme["name"] == "SLCC"
    # Deep Petrol, Muted Teal, Deep Sand, Clay - the validated categorical set.
    assert theme["dataColors"][:4] == ["#173F4F", "#5F9EA0", "#C9A96A", "#A0524A"]
    assert theme["background"].upper() == "#F4F1EA"
    # No pure red anywhere: the palette bans it.
    assert "#FF0000" not in str(theme).upper()
