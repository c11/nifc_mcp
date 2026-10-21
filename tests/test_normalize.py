from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from wfigs_mcp.normalize import Scope, normalize_feature


def test_normalizes_recorded_ytd_feature() -> None:
    fixture = json.loads(
        (Path(__file__).parent / "fixtures" / "ytd_feature.json").read_text()
    )

    fire = normalize_feature(fixture, Scope.YEAR_TO_DATE)

    assert fire.irwin_id == "9B057B06-06BA-4946-A12E-3ED4344F3D00"
    assert fire.name == "SPOUT SPRINGS"
    assert fire.state == "WY"
    assert fire.acres == 1.7000358136788434
    assert fire.acres_source == "poly_Acres_AutoCalc"
    assert fire.percent_contained is None
    assert fire.discovery_date == datetime(2026, 10, 5, 20, 44, tzinfo=UTC)
    assert fire.perimeter_updated_source == "poly_PolygonDateTime"
    assert fire.centroid is not None and fire.centroid.lon == -109.0
    assert fire.bbox is not None and fire.bbox.ymax == 44.6


def test_falls_back_for_nullable_fields() -> None:
    feature = {
        "attributes": {
            "poly_IncidentName": "Fallback",
            "poly_GISAcres": 12.5,
            "poly_Acres_AutoCalc": None,
            "poly_CreateDate": 1_700_000_000_000,
            "poly_DateCurrent": None,
            "poly_PolygonDateTime": None,
            "poly_IRWINID": "{abc}",
            "attr_IncidentName": None,
            "attr_FireDiscoveryDateTime": None,
            "attr_IncidentTypeCategory": "RX",
            "attr_POOState": None,
        }
    }

    fire = normalize_feature(feature, Scope.ACTIVE)

    assert fire.name == "Fallback"
    assert fire.irwin_id == "ABC"
    assert fire.acres == 12.5
    assert fire.acres_source == "poly_GISAcres"
    assert fire.perimeter_updated_source == "poly_CreateDate"
    assert fire.incident_type == "prescribed_fire"


def test_capture_time_wins_over_newer_edit_time() -> None:
    fixture = json.loads(
        (Path(__file__).parent / "fixtures" / "current_feature.json").read_text()
    )

    fire = normalize_feature(fixture, Scope.ACTIVE)

    assert fire.perimeter_updated_at == datetime(2026, 6, 21, 15, 43, 27, 385000, UTC)
    assert fire.perimeter_updated_source == "poly_PolygonDateTime"
