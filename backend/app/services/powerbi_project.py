"""The SLCC report, built as a Power BI project people can just open.

Handing somebody a data endpoint is handing them a morning of work: seven
queries to write, every column to type by hand, nine relationships to draw and
ten measures to key in. The first person who tried it here spent that morning,
and the columns still arrived as text - which is not a beginner's mistake, it is
what a JSON source does when nobody types it.

So the endpoint stays for whoever wants to build their own model, and this
builds the one SLCC already knows how to draw. A `.pbip` is a folder of JSON:
the semantic model in TMSL, the report layout beside it. Power BI Desktop opens
one as a finished report, which means the whole thing can be written here.

The file carries no data - only the queries that fetch it. Open it with the API
down and you get an empty report, not a stale one. That is the correct failure:
a BI file that quietly serves last month's figures is worse than one that says
it cannot reach the source.
"""

from __future__ import annotations

import io
import json
import zipfile
from typing import Any

from sqlalchemy.orm import Session

from app.services.analytics_service import powerbi_datasets, powerbi_theme

NAME = "SLCC"

#: The timestamp each fact table is dated by. `dim_date` holds plain dates and
#: the facts hold microsecond timestamps, so a direct join never matches a
#: single row - every fact gets a date-only column cut from the one named here.
DATE_SOURCE = {
    "fact_lots": "received_at",
    "fact_stock_movements": "occurred_at",
    "fact_quality": "inspected_at",
    "fact_production_requests": "created_on",
}

#: Dimension <- fact, single direction, always. A calendar that can be filtered
#: by the facts it explains is a calendar nobody can reason about.
RELATIONS = [
    ("fact_lots", "part_reference", "dim_stock", "part_reference"),
    ("fact_quality", "part_reference", "dim_stock", "part_reference"),
    ("fact_production_requests", "part_reference", "dim_stock", "part_reference"),
    ("fact_stock_movements", "part_reference", "dim_stock", "part_reference"),
    ("fact_lots", "location", "dim_locations", "location_code"),
    ("fact_lots", "date", "dim_date", "date"),
    ("fact_quality", "date", "dim_date", "date"),
    ("fact_production_requests", "date", "dim_date", "date"),
    ("fact_stock_movements", "date", "dim_date", "date"),
]

#: The same ten measures the API publishes, with the format string attached.
#: A rate that reads `0,632` instead of `63,2 %` gets rounded to "0" in
#: somebody's slide - the format is part of the measure, not decoration.
MEASURE_FORMAT = {
    "Total Stock": "#,0",
    "Open Demand": "#,0",
    "Issued Quantity": "#,0",
    "Blocked Lots": "#,0",
    "References At Risk": "#,0",
    "Stock Coverage": "#,0.0",
    "Conformity Rate": "0.0%",
    "Non-Conformity Rate": "0.0%",
    "Warehouse Occupancy": "0.0%",
    "Service Rate": "0.0%",
}

M_TYPE = {
    "string": "type text",
    "int64": "Int64.Type",
    "double": "type number",
    "boolean": "type logical",
    "dateTime": "type datetime",
    "date": "type date",
}
TMSL_TYPE = {
    "string": "string",
    "int64": "int64",
    "double": "double",
    "boolean": "boolean",
    "dateTime": "dateTime",
    "date": "dateTime",
}
COLUMN_FORMAT = {
    "int64": "0",
    "double": "0.00",
    "dateTime": "General Date",
    "date": "Long Date",
}


def _kind(values: list[Any]) -> str:
    """The narrowest type every value fits.

    Text is the fallback, never a guess: one stray string in a numeric column
    and the whole column stays text, which loads correctly and sums to nothing,
    rather than loading as a number and dropping rows.
    """
    present = [v for v in values if v is not None]
    if not present:
        return "string"
    if all(isinstance(v, bool) for v in present):
        return "boolean"
    if all(isinstance(v, int) and not isinstance(v, bool) for v in present):
        return "int64"
    if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in present):
        return "double"
    if all(isinstance(v, str) and len(v) >= 19 and v[10:11] == "T" for v in present):
        return "dateTime"
    if all(isinstance(v, str) and len(v) == 10 and v[4:5] == "-" for v in present):
        return "date"
    return "string"


def _column_kinds(dataset: dict) -> dict[str, str]:
    rows = dataset["rows"]
    return {c: _kind([r.get(c) for r in rows]) for c in dataset["columns"]}


def _partition_m(dataset: dict, endpoint: str) -> list[str]:
    """One query: fetch the catalogue, pick one dataset, type every column.

    The culture is pinned to `en-US` because the dates arrive in ISO order.
    Left to the machine's locale, `2026-07-22` is read as a French date on one
    PC and refused on another - a report that only opens on its author's laptop.
    """
    name = dataset["name"]
    kinds = _column_kinds(dataset)
    types = ", ".join('{"%s", %s}' % (c, M_TYPE[k]) for c, k in kinds.items())
    lines = [
        "let",
        '    Source = Json.Document(Web.Contents("%s")),' % endpoint,
        '    Jeu = List.First(List.Select(Source[datasets], each [name] = "%s")),' % name,
        "    Table = Table.FromRecords(Jeu[rows]),",
        '    Types = Table.TransformColumnTypes(Table, {%s}, "en-US")' % types,
    ]
    source = DATE_SOURCE.get(name)
    if source:
        lines[-1] += ","
        lines.append(
            '    AvecDate = Table.AddColumn(Types, "date", '
            "each Date.From([%s]), type date)" % source
        )
        lines += ["in", "    AvecDate"]
    else:
        lines += ["in", "    Types"]
    return lines


def _column(name: str, kind: str) -> dict:
    column = {
        "name": name,
        "dataType": TMSL_TYPE[kind],
        "sourceColumn": name,
        "summarizeBy": "sum" if kind in ("int64", "double") else "none",
        "annotations": [{"name": "SummarizationSetBy", "value": "Automatic"}],
    }
    if kind in COLUMN_FORMAT:
        column["formatString"] = COLUMN_FORMAT[kind]
    return column


def _table(dataset: dict, endpoint: str) -> dict:
    name = dataset["name"]
    kinds = _column_kinds(dataset)
    columns = [_column(c, k) for c, k in kinds.items()]
    if name in DATE_SOURCE:
        columns.append(_column("date", "date"))
    return {
        "name": name,
        "columns": columns,
        "partitions": [
            {
                "name": name,
                "mode": "import",
                "source": {"type": "m", "expression": _partition_m(dataset, endpoint)},
            }
        ],
        "annotations": [{"name": "PBI_ResultType", "value": "Table"}],
    }


def _measures_table(measures: list[dict]) -> dict:
    """The measures get their own table.

    They have no home otherwise, and the first one lands wherever the cursor
    happened to be - a conformity rate filed under the calendar. It is
    cosmetic until somebody opens the model in front of a room.
    """
    return {
        "name": "Mesures",
        "columns": [
            {
                "name": "Column1",
                "dataType": "string",
                "sourceColumn": "Column1",
                "isHidden": True,
                "summarizeBy": "none",
                "annotations": [{"name": "SummarizationSetBy", "value": "Automatic"}],
            }
        ],
        "measures": [
            {
                "name": measure["name"],
                "expression": measure["expression"].strip(),
                "formatString": MEASURE_FORMAT.get(measure["name"], "#,0"),
                "description": measure.get("description", ""),
            }
            for measure in measures
        ],
        "partitions": [
            {
                "name": "Mesures",
                "mode": "import",
                "source": {
                    "type": "m",
                    "expression": [
                        "let",
                        "    Source = Table.FromRows({}, type table [Column1 = text])",
                        "in",
                        "    Source",
                    ],
                },
            }
        ],
    }


def _model(catalog: dict, endpoint: str) -> dict:
    datasets = catalog["datasets"]
    names = [d["name"] for d in datasets]
    present = set(names)
    return {
        "name": NAME,
        "compatibilityLevel": 1567,
        "model": {
            "culture": "en-US",
            "dataAccessOptions": {
                "legacyRedirects": True,
                "returnErrorValuesAsNull": True,
            },
            "defaultPowerBIDataSourceVersion": "powerBI_V3",
            "sourceQueryCulture": "en-US",
            "tables": [_table(d, endpoint) for d in datasets]
            + [_measures_table(catalog["measures"])],
            # A relationship naming a table the catalogue did not ship would
            # refuse the whole model, so the pairs are filtered against what
            # actually arrived rather than assumed.
            "relationships": [
                {
                    "name": "rel-%d" % index,
                    "fromTable": from_table,
                    "fromColumn": from_column,
                    "toTable": to_table,
                    "toColumn": to_column,
                }
                for index, (from_table, from_column, to_table, to_column) in enumerate(
                    r for r in RELATIONS if r[0] in present and r[2] in present
                )
            ],
            "annotations": [
                {"name": "PBI_QueryOrder", "value": json.dumps(names + ["Mesures"])}
            ],
        },
    }


# ------------------------------------------------------------------- the page


def _title(text: str) -> dict:
    return {
        "title": [
            {
                "properties": {
                    "show": {"expr": {"Literal": {"Value": "true"}}},
                    "text": {"expr": {"Literal": {"Value": "'%s'" % text}}},
                }
            }
        ]
    }


def _container(x: int, y: int, z: int, w: int, h: int, config: dict) -> dict:
    # `filters` is not optional: the renderer reads it on every container and
    # abandons the whole page if one is missing.
    return {
        "x": x,
        "y": y,
        "z": z,
        "width": w,
        "height": h,
        "config": json.dumps(config),
        "filters": "[]",
    }


def _layout(x: int, y: int, z: int, w: int, h: int) -> list[dict]:
    return [
        {
            "id": 0,
            "position": {
                "x": x,
                "y": y,
                "z": z,
                "width": w,
                "height": h,
                "tabOrder": z * 10,
            },
        }
    ]


def _card(z: int, measure: str, title: str, x: int, y: int, w: int = 288, h: int = 118):
    config = {
        "name": "card%d" % z,
        "layouts": _layout(x, y, z, w, h),
        "singleVisual": {
            "visualType": "card",
            "projections": {"Values": [{"queryRef": "Mesures.%s" % measure}]},
            "prototypeQuery": {
                "Version": 2,
                "From": [{"Name": "m", "Entity": "Mesures", "Type": 0}],
                "Select": [
                    {
                        "Measure": {
                            "Expression": {"SourceRef": {"Source": "m"}},
                            "Property": measure,
                        },
                        "Name": "Mesures.%s" % measure,
                        "NativeReferenceName": measure,
                    }
                ],
            },
            "drillFilterOtherVisuals": True,
            # Auto units turn 30 526 into "31K". The abbreviation hides the
            # figure the report was opened to read.
            "objects": {
                "labels": [
                    {
                        "properties": {
                            "labelDisplayUnits": {"expr": {"Literal": {"Value": "0D"}}}
                        }
                    }
                ]
            },
            "vcObjects": _title(title),
        },
    }
    return _container(x, y, z, w, h, config)


def _chart(
    z: int,
    visual_type: str,
    entity: str,
    category: str,
    value: str,
    aggregation: int,
    title: str,
    x: int,
    y: int,
    w: int,
    h: int,
):
    """`aggregation`: 0 sums the column, 1 averages it."""
    function_name = {0: "Sum", 1: "Average"}[aggregation]
    value_ref = "%s(%s.%s)" % (function_name, entity, value)
    config = {
        "name": "vis%d" % z,
        "layouts": _layout(x, y, z, w, h),
        "singleVisual": {
            "visualType": visual_type,
            "projections": {
                "Category": [{"queryRef": "%s.%s" % (entity, category)}],
                "Y": [{"queryRef": value_ref}],
            },
            "prototypeQuery": {
                "Version": 2,
                "From": [{"Name": "e", "Entity": entity, "Type": 0}],
                "Select": [
                    {
                        "Column": {
                            "Expression": {"SourceRef": {"Source": "e"}},
                            "Property": category,
                        },
                        "Name": "%s.%s" % (entity, category),
                        "NativeReferenceName": category,
                    },
                    {
                        "Aggregation": {
                            "Expression": {
                                "Column": {
                                    "Expression": {"SourceRef": {"Source": "e"}},
                                    "Property": value,
                                }
                            },
                            "Function": aggregation,
                        },
                        "Name": value_ref,
                        "NativeReferenceName": "%s of %s" % (function_name, value),
                    },
                ],
            },
            "drillFilterOtherVisuals": True,
            "vcObjects": _title(title),
        },
    }
    return _container(x, y, z, w, h, config)


def _slicer(z: int, entity: str, column: str, title: str, x: int, y: int, w: int, h: int):
    config = {
        "name": "vis%d" % z,
        "layouts": _layout(x, y, z, w, h),
        "singleVisual": {
            "visualType": "slicer",
            "projections": {"Values": [{"queryRef": "%s.%s" % (entity, column)}]},
            "prototypeQuery": {
                "Version": 2,
                "From": [{"Name": "s", "Entity": entity, "Type": 0}],
                "Select": [
                    {
                        "Column": {
                            "Expression": {"SourceRef": {"Source": "s"}},
                            "Property": column,
                        },
                        "Name": "%s.%s" % (entity, column),
                        "NativeReferenceName": column,
                    }
                ],
            },
            "drillFilterOtherVisuals": True,
            "vcObjects": _title(title),
        },
    }
    return _container(x, y, z, w, h, config)


def _table_visual(
    z: int, entity: str, columns: list[str], title: str, x: int, y: int, w: int, h: int
):
    select, projections = [], []
    for column in columns:
        select.append(
            {
                "Column": {
                    "Expression": {"SourceRef": {"Source": "t"}},
                    "Property": column,
                },
                "Name": "%s.%s" % (entity, column),
                "NativeReferenceName": column,
            }
        )
        projections.append({"queryRef": "%s.%s" % (entity, column)})
    config = {
        "name": "vis%d" % z,
        "layouts": _layout(x, y, z, w, h),
        "singleVisual": {
            "visualType": "tableEx",
            "projections": {"Values": projections},
            "prototypeQuery": {
                "Version": 2,
                "From": [{"Name": "t", "Entity": entity, "Type": 0}],
                "Select": select,
            },
            "drillFilterOtherVisuals": True,
            "vcObjects": _title(title),
        },
    }
    return _container(x, y, z, w, h, config)


def _report() -> dict:
    """One page: four figures across the top, then the charts that explain them.

    Nothing overlaps and nothing runs off the edge - a 1280x720 page fits this
    layout exactly once, with a 16px gutter throughout.
    """
    containers = [
        _card(1, "Total Stock", "Stock total (pieces)", 16, 16),
        _card(2, "Conformity Rate", "Taux de conformite", 320, 16),
        _card(3, "Warehouse Occupancy", "Occupation entrepot", 624, 16),
        _card(4, "Blocked Lots", "Lots en cage rouge", 928, 16),
        _chart(
            5, "columnChart", "dim_locations", "zone", "occupancy_percent", 1,
            "Occupation moyenne par zone", 16, 150, 608, 260,
        ),
        # Suppliers get horizontal bars: their names are long, and long labels
        # under vertical columns are printed at 45 degrees or truncated.
        _chart(
            6, "barChart", "fact_quality", "supplier", "defect_rate_percent", 1,
            "Taux de defauts moyen par fournisseur", 640, 150, 624, 260,
        ),
        _chart(
            7, "lineChart", "fact_lots", "date", "quantity_received", 0,
            "Quantites receptionnees dans le temps", 16, 426, 608, 278,
        ),
        _slicer(8, "dim_date", "date", "Periode", 640, 426, 288, 278),
        _table_visual(
            9, "dim_stock",
            ["part_reference", "designation", "quantity_available", "safety_stock"],
            "Stock contre stock de securite", 944, 426, 320, 278,
        ),
    ]
    return {
        "id": 0,
        # The base theme is declared as a resource package. Without it the theme
        # lookup fails at render time and the page never draws, under the
        # unhelpful heading "Failed to load the report".
        "resourcePackages": [
            {
                "resourcePackage": {
                    "disabled": False,
                    "items": [
                        {
                            "name": "CY24SU10",
                            "path": "BaseThemes/CY24SU10.json",
                            "type": 202,
                        }
                    ],
                    "name": "SharedResources",
                    "type": 2,
                }
            }
        ],
        "config": json.dumps(
            {
                "version": "5.55",
                "themeCollection": {
                    "baseTheme": {"name": "CY24SU10", "version": "5.55", "type": 2}
                },
                "activeSectionIndex": 0,
                "defaultDrillFilterOtherVisuals": True,
                "settings": {
                    "useStylableVisualContainerHeader": True,
                    "allowChangeFilterTypes": True,
                },
            }
        ),
        "layoutOptimization": 0,
        "sections": [
            {
                "id": 0,
                "name": "SupervisionSLCC",
                "displayName": "Supervision",
                "filters": "[]",
                "ordinal": 0,
                "visualContainers": containers,
                "config": "{}",
                "displayOption": 1,
                "width": 1280,
                "height": 720,
            }
        ],
    }


README = """SLCC - rapport Power BI
=======================

1. Decompressez ce dossier ou vous voulez (le Bureau convient).
2. Double-cliquez sur SLCC.pbip.
3. Dans Power BI : Home > Refresh.

Le fichier ne contient aucune donnee : il contient les requetes qui vont les
chercher. L'API SLCC doit donc tourner pour que Refresh fonctionne. Ouvert API
eteinte, le rapport s'affiche vide - pas avec de vieux chiffres.

Adresse lue par les sept requetes :
    {endpoint}

Couleurs SLCC (facultatif) :
    View > Themes > Browse for themes > SLCC-theme.json

Ce qu'il y a dedans
-------------------
{tables} tables typees, {relations} relations, {measures} mesures, 9 visuels sur
une page. Le curseur de periode pilote toute la page.
"""


def build_project(db: Session, *, endpoint: str) -> bytes:
    """The whole project as a zip, built from the same catalogue the site reads.

    `endpoint` is the URL the queries will call. It is passed in rather than
    hardcoded because the report is only useful if it points at the API that
    served it - a file that always says `127.0.0.1:8001` is wrong the first
    time anybody moves the port.
    """
    catalog = powerbi_datasets(db)
    model = _model(catalog, endpoint)
    report = _report()

    def dumps(payload: dict) -> str:
        return json.dumps(payload, indent=2, ensure_ascii=False)

    files = {
        "SLCC.pbip": dumps(
            {
                "$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
                "version": "1.0",
                "artifacts": [{"report": {"path": "SLCC.Report"}}],
                "settings": {"enableAutoRecovery": True},
            }
        ),
        "SLCC.SemanticModel/.platform": dumps(
            {
                "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
                "metadata": {"type": "SemanticModel", "displayName": NAME},
                "config": {
                    "version": "2.0",
                    "logicalId": "c1f7a2d8-1111-4aaa-9001-0000000000a1",
                },
            }
        ),
        "SLCC.SemanticModel/definition.pbism": dumps(
            {
                "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
                "version": "4.2",
                "settings": {},
            }
        ),
        "SLCC.SemanticModel/model.bim": dumps(model),
        "SLCC.Report/.platform": dumps(
            {
                "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
                "metadata": {"type": "Report", "displayName": NAME},
                "config": {
                    "version": "2.0",
                    "logicalId": "c1f7a2d8-2222-4bbb-9002-0000000000b2",
                },
            }
        ),
        "SLCC.Report/definition.pbir": dumps(
            {
                "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/1.0.0/schema.json",
                "version": "1.0",
                "datasetReference": {"byPath": {"path": "../SLCC.SemanticModel"}},
            }
        ),
        "SLCC.Report/report.json": dumps(report),
        "SLCC-theme.json": dumps(powerbi_theme()),
        "LISEZ-MOI.txt": README.format(
            endpoint=endpoint,
            tables=len(model["model"]["tables"]),
            relations=len(model["model"]["relationships"]),
            measures=len(catalog["measures"]),
        ),
    }

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path, content in files.items():
            archive.writestr(path, content)
    return buffer.getvalue()
