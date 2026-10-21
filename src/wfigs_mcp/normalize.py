from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Scope(StrEnum):
    ACTIVE = "active"
    YEAR_TO_DATE = "year_to_date"


class IncidentType(StrEnum):
    WILDFIRE = "wildfire"
    PRESCRIBED_FIRE = "prescribed_fire"


class Coordinate(BaseModel):
    lat: float
    lon: float


class BoundingBox(BaseModel):
    xmin: float
    ymin: float
    xmax: float
    ymax: float


class NormalizedFire(BaseModel):
    model_config = ConfigDict(extra="forbid")

    irwin_id: str
    name: str
    state: str | None
    county: str | None
    acres: float | None
    acres_source: str | None
    percent_contained: float | None
    discovery_date: datetime | None
    perimeter_updated_at: datetime | None
    perimeter_updated_source: str | None
    incident_type: IncidentType | None
    unit_id: str | None
    agency: str | None
    centroid: Coordinate | None
    bbox: BoundingBox | None
    dataset: Scope


class DetailedFire(NormalizedFire):
    polygon_name: str | None = None
    reported_incident_acres: float | None = None
    reported_incident_acres_source: str | None = None
    containment_date: datetime | None = None
    control_date: datetime | None = None
    fire_out_date: datetime | None = None
    fire_cause: str | None = None
    incident_description: str | None = None
    protecting_agency: str | None = None
    jurisdictional_agency: str | None = None
    is_complex_child: bool | None = None
    complex_name: str | None = None
    complex_irwin_id: str | None = None
    extra_attributes: dict[str, Any] = Field(default_factory=dict)


NORMALIZED_OUT_FIELDS = (
    "poly_IncidentName,poly_GISAcres,poly_Acres_AutoCalc,poly_CreateDate,"
    "poly_DateCurrent,poly_PolygonDateTime,poly_IRWINID,attr_IncidentName,"
    "attr_IncidentSize,attr_FinalAcres,attr_PercentContained,"
    "attr_FireDiscoveryDateTime,attr_IncidentTypeCategory,attr_POOState,"
    "attr_POOCounty,attr_POOJurisdictionalAgency,attr_POOJurisdictionalUnit,"
    "attr_POOProtectingAgency,attr_POOProtectingUnit,attr_IrwinID"
)

DETAIL_OUT_FIELDS = (
    f"{NORMALIZED_OUT_FIELDS},attr_ContainmentDateTime,attr_ControlDateTime,"
    "attr_FireOutDateTime,attr_FireCause,attr_IncidentShortDescription,"
    "attr_IsCpxChild,attr_CpxName,attr_CpxID"
)


def normalize_feature(feature: dict[str, Any], dataset: Scope) -> NormalizedFire:
    attributes = _attributes(feature)
    irwin_id = _first_text(attributes, "poly_IRWINID", "attr_IrwinID")
    name = _first_text(attributes, "attr_IncidentName", "poly_IncidentName")
    if irwin_id is None or name is None:
        raise ValueError("Feature is missing its IRWIN ID or incident name")

    acres, acres_source = _first_number_with_source(
        attributes, "poly_Acres_AutoCalc", "poly_GISAcres"
    )
    perimeter_updated, perimeter_source = _first_date_with_source(
        attributes, "poly_PolygonDateTime", "poly_DateCurrent", "poly_CreateDate"
    )
    state = _first_text(attributes, "attr_POOState")
    if state and state.startswith("US-"):
        state = state[3:]

    return NormalizedFire(
        irwin_id=_canonical_irwin_id(irwin_id),
        name=name,
        state=state,
        county=_first_text(attributes, "attr_POOCounty"),
        acres=acres,
        acres_source=acres_source,
        percent_contained=_number(attributes.get("attr_PercentContained")),
        discovery_date=_date(attributes.get("attr_FireDiscoveryDateTime")),
        perimeter_updated_at=perimeter_updated,
        perimeter_updated_source=perimeter_source,
        incident_type=_incident_type(attributes.get("attr_IncidentTypeCategory")),
        unit_id=_first_text(
            attributes, "attr_POOProtectingUnit", "attr_POOJurisdictionalUnit"
        ),
        agency=_first_text(
            attributes, "attr_POOProtectingAgency", "attr_POOJurisdictionalAgency"
        ),
        centroid=_centroid(feature.get("centroid")),
        bbox=_bbox(feature.get("envelope")),
        dataset=dataset,
    )


def normalize_detailed_feature(feature: dict[str, Any], dataset: Scope) -> DetailedFire:
    base = normalize_feature(feature, dataset)
    attributes = _attributes(feature)
    reported_acres, reported_source = _first_number_with_source(
        attributes, "attr_FinalAcres", "attr_IncidentSize"
    )
    normalized_fields = set(DETAIL_OUT_FIELDS.split(","))
    extras = {key: value for key, value in attributes.items() if key not in normalized_fields}
    complex_child = attributes.get("attr_IsCpxChild")
    return DetailedFire(
        **base.model_dump(),
        polygon_name=_first_text(attributes, "poly_IncidentName"),
        reported_incident_acres=reported_acres,
        reported_incident_acres_source=reported_source,
        containment_date=_date(attributes.get("attr_ContainmentDateTime")),
        control_date=_date(attributes.get("attr_ControlDateTime")),
        fire_out_date=_date(attributes.get("attr_FireOutDateTime")),
        fire_cause=_first_text(attributes, "attr_FireCause"),
        incident_description=_first_text(attributes, "attr_IncidentShortDescription"),
        protecting_agency=_first_text(attributes, "attr_POOProtectingAgency"),
        jurisdictional_agency=_first_text(attributes, "attr_POOJurisdictionalAgency"),
        is_complex_child=bool(complex_child) if complex_child is not None else None,
        complex_name=_first_text(attributes, "attr_CpxName"),
        complex_irwin_id=_first_text(attributes, "attr_CpxID"),
        extra_attributes=extras,
    )


def _attributes(feature: dict[str, Any]) -> dict[str, Any]:
    attributes = feature.get("attributes")
    if not isinstance(attributes, dict):
        raise ValueError("Feature is missing attributes")
    return attributes


def _canonical_irwin_id(value: str) -> str:
    return value.strip().strip("{}").upper()


def _first_text(attributes: dict[str, Any], *names: str) -> str | None:
    for name in names:
        value = attributes.get(name)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _number(value: object) -> float | None:
    if isinstance(value, int | float) and not isinstance(value, bool):
        return float(value)
    return None


def _first_number_with_source(
    attributes: dict[str, Any], *names: str
) -> tuple[float | None, str | None]:
    for name in names:
        value = _number(attributes.get(name))
        if value is not None:
            return value, name
    return None, None


def _date(value: object) -> datetime | None:
    number = _number(value)
    if number is None:
        return None
    return datetime.fromtimestamp(number / 1_000, tz=UTC)


def _first_date_with_source(
    attributes: dict[str, Any], *names: str
) -> tuple[datetime | None, str | None]:
    for name in names:
        value = _date(attributes.get(name))
        if value is not None:
            return value, name
    return None, None


def _incident_type(value: object) -> IncidentType | None:
    if value == "WF":
        return IncidentType.WILDFIRE
    if value == "RX":
        return IncidentType.PRESCRIBED_FIRE
    return None


def _centroid(value: object) -> Coordinate | None:
    if not isinstance(value, dict):
        return None
    lon = _number(value.get("x"))
    lat = _number(value.get("y"))
    if lon is None or lat is None:
        return None
    return Coordinate(lat=lat, lon=lon)


def _bbox(value: object) -> BoundingBox | None:
    if not isinstance(value, dict):
        return None
    numbers = [_number(value.get(name)) for name in ("xmin", "ymin", "xmax", "ymax")]
    if any(number is None for number in numbers):
        return None
    xmin, ymin, xmax, ymax = numbers
    assert xmin is not None and ymin is not None and xmax is not None and ymax is not None
    return BoundingBox(xmin=xmin, ymin=ymin, xmax=xmax, ymax=ymax)
