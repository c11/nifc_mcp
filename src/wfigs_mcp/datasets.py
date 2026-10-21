from __future__ import annotations

import json
import re
from collections.abc import Sequence
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator
from shapely.geometry import mapping, shape

from .arcgis import ArcGISClient, ArcGISResponseError
from .caveats import Freshness, freshness
from .enrichment import IncidentLocationEnricher
from .geo import GEOD, proximity_to_perimeter, simplify_geometry
from .normalize import (
    DETAIL_OUT_FIELDS,
    NORMALIZED_OUT_FIELDS,
    DetailedFire,
    IncidentType,
    NormalizedFire,
    Scope,
    normalize_detailed_feature,
    normalize_feature,
)

DEFAULT_LIMIT = 25
STATE_PATTERN = re.compile(r"^[A-Z]{2}$")
VALID_STATE_CODES = frozenset(
    {
        "AK", "AL", "AR", "AS", "AZ", "CA", "CO", "CT", "DC", "DE", "FL",
        "GA", "GU", "HI", "IA", "ID", "IL", "IN", "KS", "KY", "LA", "MA",
        "MD", "ME", "MI", "MN", "MO", "MP", "MS", "MT", "NC", "ND", "NE",
        "NH", "NJ", "NM", "NV", "NY", "OH", "OK", "OR", "PA", "PR", "RI",
        "SC", "SD", "TN", "TX", "UT", "VA", "VI", "VT", "WA", "WI", "WV",
        "WY",
    }
)


class SortBy(StrEnum):
    ACRES = "acres"
    DISCOVERY_DATE = "discovery_date"
    PERIMETER_UPDATED_AT = "perimeter_updated_at"


class GroupBy(StrEnum):
    STATE = "state"
    INCIDENT_TYPE = "incident_type"
    MONTH = "month"
    AGENCY = "agency"


class SearchFilters(BaseModel):
    state: str | None = None
    name_contains: str | None = None
    min_acres: float | None = Field(default=None, ge=0)
    max_acres: float | None = Field(default=None, ge=0)
    discovered_after: date | None = None
    discovered_before: date | None = None
    incident_type: IncidentType | None = None
    min_percent_contained: float | None = Field(default=None, ge=0, le=100)
    max_percent_contained: float | None = Field(default=None, ge=0, le=100)

    @model_validator(mode="after")
    def validate_ranges(self) -> SearchFilters:
        if (
            self.min_acres is not None
            and self.max_acres is not None
            and self.min_acres > self.max_acres
        ):
            raise ValueError("min_acres cannot exceed max_acres")
        if (
            self.min_percent_contained is not None
            and self.max_percent_contained is not None
            and self.min_percent_contained > self.max_percent_contained
        ):
            raise ValueError("min_percent_contained cannot exceed max_percent_contained")
        if (
            self.discovered_after is not None
            and self.discovered_before is not None
            and self.discovered_after > self.discovered_before
        ):
            raise ValueError("discovered_after cannot be later than discovered_before")
        return self

    def where_clause(self) -> str:
        clauses: list[str] = ["1=1"]
        if self.state:
            state = validate_state(self.state)
            clauses.append(f"attr_POOState = 'US-{state}'")
        if self.name_contains:
            value = _sql_text(self.name_contains.upper())
            clauses.append(
                f"(UPPER(attr_IncidentName) LIKE '%{value}%' "
                f"OR UPPER(poly_IncidentName) LIKE '%{value}%')"
            )
        if self.min_acres is not None:
            clauses.append(f"poly_Acres_AutoCalc >= {self.min_acres}")
        if self.max_acres is not None:
            clauses.append(f"poly_Acres_AutoCalc <= {self.max_acres}")
        if self.discovered_after:
            timestamp = f"{self.discovered_after.isoformat()} 00:00:00"
            clauses.append(
                f"attr_FireDiscoveryDateTime >= TIMESTAMP '{timestamp}'"
            )
        if self.discovered_before:
            timestamp = f"{self.discovered_before.isoformat()} 23:59:59"
            clauses.append(
                f"attr_FireDiscoveryDateTime <= TIMESTAMP '{timestamp}'"
            )
        if self.incident_type:
            category = "WF" if self.incident_type is IncidentType.WILDFIRE else "RX"
            clauses.append(f"attr_IncidentTypeCategory = '{category}'")
        if self.min_percent_contained is not None:
            clauses.append(f"attr_PercentContained >= {self.min_percent_contained}")
        if self.max_percent_contained is not None:
            clauses.append(f"attr_PercentContained <= {self.max_percent_contained}")
        return " AND ".join(clauses)


class SearchResponse(BaseModel):
    dataset: Scope
    fires: list[NormalizedFire]
    total_count: int
    truncated: bool
    freshness: Freshness


class FireResponse(BaseModel):
    dataset: Scope
    status: Literal["found", "not_found", "ambiguous"]
    message: str
    fire: DetailedFire | None = None
    candidates: list[NormalizedFire] = Field(default_factory=list)
    freshness: Freshness


class NearbyFire(BaseModel):
    fire: NormalizedFire
    distance_miles: float
    inside: bool
    bearing_degrees: float | None


class NearbyResponse(BaseModel):
    dataset: Scope
    fires: list[NearbyFire]
    total_count: int
    truncated: bool
    freshness: Freshness


class SummaryGroup(BaseModel):
    group: str
    count: int
    total_perimeter_acres: float


class SummaryResponse(BaseModel):
    dataset: Scope
    group_by: GroupBy
    groups: list[SummaryGroup]
    acreage_source: str = "poly_Acres_AutoCalc"
    note: str = (
        "Perimeter acreage is not definitive burned area; overlapping complex and child "
        "perimeters can be double-counted."
    )
    freshness: Freshness


class PerimeterResponse(BaseModel):
    dataset: Scope
    irwin_id: str
    name: str
    format: Literal["geojson", "wkt", "bbox_only"]
    geometry: dict[str, Any] | str
    vertices_before: int
    vertices_after: int
    simplify_tolerance_m: float
    message: str = "Found the requested perimeter."
    freshness: Freshness


class DatasetService:
    def __init__(
        self,
        client: ArcGISClient,
        current_layer_url: str,
        ytd_layer_url: str,
        *,
        max_limit: int = 200,
        vertex_cap: int = 10_000,
        incident_location_enricher: IncidentLocationEnricher | None = None,
    ) -> None:
        self.client = client
        self.layer_urls = {
            Scope.ACTIVE: current_layer_url.rstrip("/"),
            Scope.YEAR_TO_DATE: ytd_layer_url.rstrip("/"),
        }
        self.max_limit = max_limit
        self.vertex_cap = vertex_cap
        self.incident_location_enricher = incident_location_enricher
        self.latest_perimeter_seen: dict[Scope, datetime | None] = {
            Scope.ACTIVE: None,
            Scope.YEAR_TO_DATE: None,
        }

    async def search_fires(
        self,
        filters: SearchFilters,
        *,
        scope: Scope = Scope.ACTIVE,
        sort_by: SortBy = SortBy.ACRES,
        limit: int = DEFAULT_LIMIT,
    ) -> SearchResponse:
        limit = self._validate_limit(limit)
        where = filters.where_clause()
        total_count, count_as_of = await self._count(scope, where)
        sort_field = {
            SortBy.ACRES: "poly_Acres_AutoCalc DESC",
            SortBy.DISCOVERY_DATE: "attr_FireDiscoveryDateTime DESC",
            SortBy.PERIMETER_UPDATED_AT: "poly_PolygonDateTime DESC",
        }[sort_by]
        result = await self.client.query_all(
            self.layer_urls[scope],
            {
                "where": where,
                "outFields": NORMALIZED_OUT_FIELDS,
                "returnGeometry": False,
                "returnCentroid": True,
                "returnEnvelope": True,
                "orderByFields": sort_field,
            },
            max_features=limit,
        )
        fires = [normalize_feature(feature, scope) for feature in result.features]
        data_as_of = max(result.fetched_at, count_as_of)
        self._record_latest(scope, fires)
        return SearchResponse(
            dataset=scope,
            fires=fires,
            total_count=total_count,
            truncated=total_count > len(fires),
            freshness=freshness(data_as_of, [fire.perimeter_updated_at for fire in fires]),
        )

    async def get_fire(
        self,
        *,
        scope: Scope = Scope.ACTIVE,
        irwin_id: str | None = None,
        name: str | None = None,
        state: str | None = None,
    ) -> FireResponse:
        if bool(irwin_id) == bool(name):
            raise ValueError("Provide exactly one of irwin_id or name")
        where = _identity_where(irwin_id=irwin_id, name=name, state=state)
        response = await self._get_fire_in_scope(scope, where)
        if response.status != "not_found" or scope is Scope.YEAR_TO_DATE:
            return response
        fallback = await self._get_fire_in_scope(Scope.YEAR_TO_DATE, where)
        if fallback.status == "found":
            fallback.message = "Not currently active; found in the year-to-date dataset."
        elif fallback.status == "ambiguous":
            fallback.message = (
                "Not found among active fires; multiple year-to-date candidates matched."
            )
        else:
            fallback.message = "No matching fire was found in active or year-to-date data."
        return fallback

    async def fires_near(
        self,
        lat: float,
        lon: float,
        radius_miles: float = 25,
        *,
        scope: Scope = Scope.ACTIVE,
        limit: int = DEFAULT_LIMIT,
    ) -> NearbyResponse:
        if not -90 <= lat <= 90 or not -180 <= lon <= 180:
            raise ValueError("lat must be -90..90 and lon must be -180..180")
        if not 0 < radius_miles <= 250:
            raise ValueError("radius_miles must be greater than 0 and at most 250")
        limit = self._validate_limit(limit)
        envelope = _radius_envelope(lat, lon, radius_miles)
        result = await self.client.query_all(
            self.layer_urls[scope],
            {
                "where": "1=1",
                "geometry": ",".join(str(value) for value in envelope),
                "geometryType": "esriGeometryEnvelope",
                "inSR": 4326,
                "spatialRel": "esriSpatialRelIntersects",
                "outFields": NORMALIZED_OUT_FIELDS,
                "returnGeometry": True,
                "returnCentroid": True,
                "returnEnvelope": True,
                "outSR": 4326,
            },
        )
        nearby: list[NearbyFire] = []
        for feature in result.features:
            esri_geometry = feature.get("geometry")
            if not isinstance(esri_geometry, dict):
                continue
            geojson = _esri_polygon_to_geojson(esri_geometry)
            proximity = proximity_to_perimeter(lat, lon, geojson)
            if proximity.distance_miles <= radius_miles:
                nearby.append(
                    NearbyFire(
                        fire=normalize_feature(feature, scope),
                        distance_miles=proximity.distance_miles,
                        inside=proximity.inside,
                        bearing_degrees=proximity.bearing_degrees,
                    )
                )
        nearby.sort(key=lambda value: value.distance_miles)
        total_count = len(nearby)
        selected = nearby[:limit]
        fires = [item.fire for item in selected]
        self._record_latest(scope, fires)
        return NearbyResponse(
            dataset=scope,
            fires=selected,
            total_count=total_count,
            truncated=total_count > len(selected),
            freshness=freshness(
                result.fetched_at, [fire.perimeter_updated_at for fire in fires]
            ),
        )

    async def summarize_fires(
        self,
        group_by: GroupBy,
        filters: SearchFilters,
        *,
        scope: Scope = Scope.ACTIVE,
    ) -> SummaryResponse:
        if group_by is GroupBy.MONTH:
            return await self._summarize_month(filters, scope)
        if group_by is GroupBy.AGENCY:
            return await self._summarize_agency(filters, scope)
        field = {
            GroupBy.STATE: "attr_POOState",
            GroupBy.INCIDENT_TYPE: "attr_IncidentTypeCategory",
        }[group_by]
        payload = await self.client.request_json(
            f"{self.layer_urls[scope]}/query",
            {
                "f": "json",
                "where": filters.where_clause(),
                "outStatistics": json.dumps(
                    [
                        {
                            "statisticType": "count",
                            "onStatisticField": "OBJECTID",
                            "outStatisticFieldName": "fire_count",
                        },
                        {
                            "statisticType": "sum",
                            "onStatisticField": "poly_Acres_AutoCalc",
                            "outStatisticFieldName": "total_acres",
                        },
                        {
                            "statisticType": "max",
                            "onStatisticField": "poly_PolygonDateTime",
                            "outStatisticFieldName": "newest_perimeter",
                        },
                        {
                            "statisticType": "min",
                            "onStatisticField": "poly_PolygonDateTime",
                            "outStatisticFieldName": "oldest_perimeter",
                        },
                    ]
                ),
                "groupByFieldsForStatistics": field,
                "orderByFields": "fire_count DESC",
                "returnGeometry": False,
            },
        )
        groups = []
        perimeter_times: list[datetime | None] = []
        for feature in payload.get("features", []):
            attributes = feature.get("attributes", {})
            raw_group = attributes.get(field)
            perimeter_times.extend(
                [
                    _epoch_date(attributes.get("newest_perimeter")),
                    _epoch_date(attributes.get("oldest_perimeter")),
                ]
            )
            groups.append(
                SummaryGroup(
                    group=_normalize_group(group_by, raw_group),
                    count=int(attributes.get("fire_count") or 0),
                    total_perimeter_acres=float(attributes.get("total_acres") or 0),
                )
            )
        data_as_of = self.client.last_response_as_of or datetime.now(UTC)
        return SummaryResponse(
            dataset=scope,
            group_by=group_by,
            groups=groups,
            freshness=freshness(data_as_of, perimeter_times),
        )

    async def get_perimeter(
        self,
        irwin_id: str,
        *,
        scope: Scope = Scope.ACTIVE,
        simplify_tolerance_m: float = 100,
        format: Literal["geojson", "wkt", "bbox_only"] = "geojson",
    ) -> PerimeterResponse:
        try:
            return await self._get_perimeter_in_scope(
                irwin_id,
                scope=scope,
                simplify_tolerance_m=simplify_tolerance_m,
                format=format,
            )
        except LookupError:
            if scope is Scope.YEAR_TO_DATE:
                raise ValueError("No perimeter found for that IRWIN ID") from None
            fallback = await self._get_perimeter_in_scope(
                irwin_id,
                scope=Scope.YEAR_TO_DATE,
                simplify_tolerance_m=simplify_tolerance_m,
                format=format,
            )
            fallback.message = "Not currently active; found in the year-to-date dataset."
            return fallback

    async def _get_perimeter_in_scope(
        self,
        irwin_id: str,
        *,
        scope: Scope,
        simplify_tolerance_m: float,
        format: Literal["geojson", "wkt", "bbox_only"],
    ) -> PerimeterResponse:
        where = _identity_where(irwin_id=irwin_id, name=None, state=None)
        response = await self.client.request_json(
            f"{self.layer_urls[scope]}/query",
            {
                "f": "geojson",
                "where": where,
                "outFields": NORMALIZED_OUT_FIELDS,
                "returnGeometry": True,
                "outSR": 4326,
                "resultRecordCount": 2,
            },
        )
        features = response.get("features", [])
        if not features:
            raise LookupError("No perimeter found")
        if len(features) != 1:
            raise ValueError(f"Expected one perimeter for IRWIN ID; found {len(features)}")
        feature = features[0]
        geometry = feature.get("geometry")
        properties = feature.get("properties")
        if not isinstance(geometry, dict) or not isinstance(properties, dict):
            raise ArcGISResponseError("GeoJSON perimeter response is malformed")
        normalized_feature = {"attributes": properties}
        fire = normalize_feature(normalized_feature, scope)
        simplified = simplify_geometry(geometry, simplify_tolerance_m, self.vertex_cap)
        if format == "geojson":
            output: dict[str, Any] | str = mapping(simplified.geometry)
        elif format == "wkt":
            output = simplified.geometry.wkt
        else:
            output = mapping(shape(geometry).envelope)
        self._record_latest(scope, [fire])
        data_as_of = self.client.last_response_as_of or datetime.now(UTC)
        return PerimeterResponse(
            dataset=scope,
            irwin_id=fire.irwin_id,
            name=fire.name,
            format=format,
            geometry=output,
            vertices_before=simplified.vertices_before,
            vertices_after=simplified.vertices_after,
            simplify_tolerance_m=simplified.tolerance_m,
            freshness=freshness(data_as_of, [fire.perimeter_updated_at]),
        )

    async def _get_fire_in_scope(self, scope: Scope, where: str) -> FireResponse:
        result = await self.client.query_all(
            self.layer_urls[scope],
            {
                "where": where,
                "outFields": DETAIL_OUT_FIELDS,
                "returnGeometry": False,
                "returnCentroid": True,
                "returnEnvelope": True,
                "orderByFields": "poly_PolygonDateTime DESC",
            },
            max_features=self.max_limit,
        )
        fires = [normalize_detailed_feature(feature, scope) for feature in result.features]
        if self.incident_location_enricher:
            for fire in fires:
                enrichment = await self.incident_location_enricher.get_attributes(fire.irwin_id)
                if enrichment:
                    fire.extra_attributes["incident_location"] = dict(enrichment)
        self._record_latest(scope, fires)
        response_freshness = freshness(
            result.fetched_at, [fire.perimeter_updated_at for fire in fires]
        )
        if not fires:
            return FireResponse(
                dataset=scope,
                status="not_found",
                message="No matching fire was found.",
                freshness=response_freshness,
            )
        if len(fires) > 1:
            normalized_fields = set(NormalizedFire.model_fields)
            return FireResponse(
                dataset=scope,
                status="ambiguous",
                message="Several incidents matched; use an IRWIN ID to select one.",
                candidates=[
                    NormalizedFire(**fire.model_dump(include=normalized_fields))
                    for fire in fires
                ],
                freshness=response_freshness,
            )
        return FireResponse(
            dataset=scope,
            status="found",
            message="Found one matching fire.",
            fire=fires[0],
            freshness=response_freshness,
        )

    async def _summarize_month(
        self, filters: SearchFilters, scope: Scope
    ) -> SummaryResponse:
        result = await self.client.query_all(
            self.layer_urls[scope],
            {
                "where": filters.where_clause(),
                "outFields": (
                    "attr_FireDiscoveryDateTime,poly_Acres_AutoCalc,poly_PolygonDateTime"
                ),
                "returnGeometry": False,
            },
        )
        grouped: dict[str, SummaryGroup] = {}
        perimeter_times: list[datetime | None] = []
        for feature in result.features:
            attributes = feature.get("attributes", {})
            perimeter_times.append(_epoch_date(attributes.get("poly_PolygonDateTime")))
            value = attributes.get("attr_FireDiscoveryDateTime")
            if not isinstance(value, int | float):
                key = "unknown"
            else:
                key = datetime.fromtimestamp(value / 1_000, tz=UTC).strftime("%Y-%m")
            group = grouped.setdefault(
                key, SummaryGroup(group=key, count=0, total_perimeter_acres=0)
            )
            group.count += 1
            acres = attributes.get("poly_Acres_AutoCalc")
            if isinstance(acres, int | float):
                group.total_perimeter_acres += float(acres)
        return SummaryResponse(
            dataset=scope,
            group_by=GroupBy.MONTH,
            groups=sorted(grouped.values(), key=lambda value: value.group),
            freshness=freshness(result.fetched_at, perimeter_times),
        )

    async def _summarize_agency(
        self, filters: SearchFilters, scope: Scope
    ) -> SummaryResponse:
        result = await self.client.query_all(
            self.layer_urls[scope],
            {
                "where": filters.where_clause(),
                "outFields": (
                    "attr_POOProtectingAgency,attr_POOJurisdictionalAgency,"
                    "poly_Acres_AutoCalc,poly_PolygonDateTime"
                ),
                "returnGeometry": False,
            },
        )
        grouped: dict[str, SummaryGroup] = {}
        perimeter_times: list[datetime | None] = []
        for feature in result.features:
            attributes = feature.get("attributes", {})
            group_name = (
                attributes.get("attr_POOProtectingAgency")
                or attributes.get("attr_POOJurisdictionalAgency")
                or "unknown"
            )
            key = str(group_name)
            group = grouped.setdefault(
                key, SummaryGroup(group=key, count=0, total_perimeter_acres=0)
            )
            group.count += 1
            acres = attributes.get("poly_Acres_AutoCalc")
            if isinstance(acres, int | float) and not isinstance(acres, bool):
                group.total_perimeter_acres += float(acres)
            perimeter_times.append(_epoch_date(attributes.get("poly_PolygonDateTime")))
        return SummaryResponse(
            dataset=scope,
            group_by=GroupBy.AGENCY,
            groups=sorted(grouped.values(), key=lambda value: (-value.count, value.group)),
            freshness=freshness(result.fetched_at, perimeter_times),
        )

    async def _count(self, scope: Scope, where: str) -> tuple[int, datetime]:
        payload = await self.client.request_json(
            f"{self.layer_urls[scope]}/query",
            {"f": "json", "where": where, "returnCountOnly": True},
        )
        count = payload.get("count")
        if not isinstance(count, int):
            raise ArcGISResponseError("ArcGIS count response omitted count")
        return count, self.client.last_response_as_of or datetime.now(UTC)

    def _validate_limit(self, limit: int) -> int:
        if not 1 <= limit <= self.max_limit:
            raise ValueError(f"limit must be between 1 and {self.max_limit}")
        return limit

    def _record_latest(self, scope: Scope, fires: Sequence[NormalizedFire]) -> None:
        values = [fire.perimeter_updated_at for fire in fires if fire.perimeter_updated_at]
        if not values:
            return
        latest = max(values)
        existing = self.latest_perimeter_seen[scope]
        self.latest_perimeter_seen[scope] = max(existing, latest) if existing else latest


def validate_state(value: str) -> str:
    normalized = value.upper()
    if not STATE_PATTERN.fullmatch(normalized) or normalized not in VALID_STATE_CODES:
        raise ValueError("state must be a valid two-letter U.S. state or territory code")
    return normalized


def _identity_where(
    *, irwin_id: str | None, name: str | None, state: str | None
) -> str:
    if irwin_id:
        try:
            canonical = str(UUID(irwin_id.strip().strip("{}"))).upper()
        except ValueError as exc:
            raise ValueError("irwin_id must be a UUID") from exc
        stored = "{" + canonical + "}"
        return f"(poly_IRWINID = '{stored}' OR attr_IrwinID = '{stored}')"
    if not name or not state:
        raise ValueError("Exact name lookup also requires state")
    escaped_name = _sql_text(name.upper())
    return (
        f"(UPPER(attr_IncidentName) = '{escaped_name}' "
        f"OR UPPER(poly_IncidentName) = '{escaped_name}') "
        f"AND attr_POOState = 'US-{validate_state(state)}'"
    )


def _sql_text(value: str) -> str:
    return value.replace("'", "''").replace("%", "\\%").replace("_", "\\_")


def _radius_envelope(lat: float, lon: float, radius_miles: float) -> tuple[float, ...]:
    distance_m = radius_miles * 1_609.344
    west_lon, _, _ = GEOD.fwd(lon, lat, 270, distance_m)
    east_lon, _, _ = GEOD.fwd(lon, lat, 90, distance_m)
    _, south_lat, _ = GEOD.fwd(lon, lat, 180, distance_m)
    _, north_lat, _ = GEOD.fwd(lon, lat, 0, distance_m)
    if west_lon > east_lon:
        west_lon, east_lon = -180.0, 180.0
    return west_lon, south_lat, east_lon, north_lat


def _esri_polygon_to_geojson(geometry: dict[str, Any]) -> dict[str, Any]:
    rings = geometry.get("rings")
    if not isinstance(rings, list) or not rings:
        raise ArcGISResponseError("ArcGIS polygon geometry omitted rings")
    polygons: list[list[list[list[float]]]] = []
    for raw_ring in rings:
        if not isinstance(raw_ring, list):
            continue
        ring = [[float(point[0]), float(point[1])] for point in raw_ring]
        signed_area = sum(
            (ring[index + 1][0] - ring[index][0])
            * (ring[index + 1][1] + ring[index][1])
            for index in range(len(ring) - 1)
        )
        if signed_area > 0 or not polygons:
            polygons.append([ring])
        else:
            polygons[-1].append(ring)
    if len(polygons) == 1:
        return {"type": "Polygon", "coordinates": polygons[0]}
    return {"type": "MultiPolygon", "coordinates": polygons}


def _normalize_group(group_by: GroupBy, value: object) -> str:
    if value is None:
        return "unknown"
    text = str(value)
    if group_by is GroupBy.STATE and text.startswith("US-"):
        return text[3:]
    if group_by is GroupBy.INCIDENT_TYPE:
        return {"WF": "wildfire", "RX": "prescribed_fire"}.get(text, text)
    return text


def _epoch_date(value: object) -> datetime | None:
    if isinstance(value, int | float) and not isinstance(value, bool):
        return datetime.fromtimestamp(value / 1_000, tz=UTC)
    return None
