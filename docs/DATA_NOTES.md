# WFIGS data discovery notes

Discovery was performed against the public ArcGIS services on
2026-10-21T19:47:43Z. Counts and null rates below are observations, not service
contracts.

## Resolved data sources

| Dataset | ArcGIS item | FeatureServer layer |
| --- | --- | --- |
| Current | `d1c32af3212341869b3c810f1a215824` | `https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/WFIGS_Interagency_Perimeters_Current/FeatureServer/0` |
| YearToDate | `7c81ab78d8464e5c9771e49b64e834e9` | `https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/WFIGS_Interagency_Perimeters_YearToDate/FeatureServer/0` |

Both items are owned by `NIFC_Authoritative`. The item titles are **WFIGS
Current Interagency Fire Perimeters** and **WFIGS 2026 Interagency Fire
Perimeters to Date**. The item `modified` values were 2025-04-04T16:24:00Z and
2026-01-02T18:29:31Z respectively; those item metadata dates are not data
freshness timestamps.

Current contains recent and ongoing records that pass NIFC's active and
fall-off rules. A record can disappear because its IRWIN status changed or
because its incident data has not been updated within the size-dependent
window. YearToDate contains qualifying incidents discovered in the current
calendar year and does not apply those fall-off rules. Neither layer contains a
perimeter for every incident.

### Year rollover discovery

The 2026 item can be found through the ArcGIS Sharing API at
`https://www.arcgis.com/sharing/rest/search` with this `q` expression:

```text
owner:NIFC_Authoritative AND type:"Feature Service" AND title:"WFIGS 2026 Interagency Fire Perimeters to Date"
```

The discovery helper should substitute the runtime UTC year, then require one
result with the exact normalized title, owner `NIFC_Authoritative`, type
`Feature Service`, an HTTPS service URL, and layer 0 geometry type
`esriGeometryPolygon`. It should fail closed on zero or multiple valid matches.
An environment URL override remains necessary for rollover delays and service
renames. Discovery must log the selected item ID and layer URL.

## Layer capabilities

The following values are the same on both layers unless noted:

| Property | Verified value |
| --- | --- |
| Layer name | `Perimeters` |
| Geometry | `esriGeometryPolygon`; no Z or M values |
| Spatial reference | WGS84, WKID 4326 |
| Object ID | `OBJECTID`, system maintained |
| `maxRecordCount` | 2,000 |
| Query formats | JSON, GeoJSON, PBF |
| Capabilities | Query, Extract |
| Pagination | Supported, including aggregated queries |
| Statistics | Supported, including grouped `outStatistics`, count distinct, percentile, and spatial aggregation |
| Ordering/distinct/having | Supported |
| Distance queries | Supported |
| Returned centroid/envelope/properties | Supported |

Live probes confirmed that:

- `f=geojson` returns a valid `FeatureCollection` with polygon geometry. Date
  properties remain epoch-millisecond numbers or null rather than ISO strings.
- `returnCentroid=true` returns `{ "x": <longitude>, "y": <latitude> }` even
  with `returnGeometry=false`.
- grouped count and sum statistics work. Grouping by `attr_POOState` and summing
  `poly_Acres_AutoCalc` succeeded.
- `resultOffset=2000&resultRecordCount=1` returned the next ordered record, so
  paging past `maxRecordCount` works. The response can still set
  `exceededTransferLimit=true`; clients must page until a short/empty page or
  until the known count is reached.

## Field families and meanings

`poly_*` fields describe the selected GIS polygon and its source. The important
ones are its source name and ID, map method, source-reported area, timestamps,
IRWIN link, source service, and NIFC's geodesic area calculation.

`attr_*` fields are joined from the IRWIN incident record (or the attribution
source named by `attr_Source`). They describe the incident rather than the
shape: incident name/type/status, reported sizes, discovery and status dates,
containment, point-of-origin geography, responsible agencies and units,
personnel, causes, strategies, and complex relationships.

`OBJECTID` and `GlobalID` identify the published feature, not the incident.
`Shape__Area` and `Shape__Length` are ArcGIS storage fields and must not be used
for geodesic user-facing measurements.

### Normalized field precedence

| Normalized value | Source and fallback |
| --- | --- |
| `irwin_id` | `poly_IRWINID`, then `attr_IrwinID`; normalize braces/case for matching but preserve a canonical display value |
| `name` | `attr_IncidentName`, then `poly_IncidentName` |
| `state` | `attr_POOState`; normalize `US-CA` to `CA` at the API boundary |
| `county` | `attr_POOCounty` |
| `acres` | `poly_Acres_AutoCalc`, then `poly_GISAcres`; always return the selected source field |
| reported incident acres | Expose separately in details: `attr_FinalAcres`, then `attr_IncidentSize`; do not silently mix this with perimeter area |
| `percent_contained` | `attr_PercentContained`; null means unknown, not zero |
| `discovery_date` | `attr_FireDiscoveryDateTime` |
| `perimeter_updated_at` | `poly_PolygonDateTime` (capture time), then `poly_DateCurrent`, then `poly_CreateDate`; return which field supplied it |
| `incident_type` | `attr_IncidentTypeCategory`: `WF` = wildfire, `RX` = prescribed fire |
| `unit_id` | `attr_POOProtectingUnit`, then `attr_POOJurisdictionalUnit` |
| agency | `attr_POOProtectingAgency`, then `attr_POOJurisdictionalAgency` |
| centroid | Server-returned polygon centroid for list/detail tools; geometry-derived nearest point for proximity calculations |

`poly_Acres_AutoCalc` is the best common perimeter-area value because NIFC
defines it as system-calculated geodesic WGS84 acres. `poly_GISAcres` is the
area supplied by the polygon source and is the fallback. `attr_IncidentSize`
and `attr_FinalAcres` are reported IRWIN incident-level values and can differ
from the currently selected polygon. Final acres is too sparse for use as the
general acreage field.

For freshness, `poly_PolygonDateTime` is more meaningful than
`poly_DateCurrent`: it represents when the perimeter was captured, whereas
`poly_DateCurrent` is when the source polygon record was last edited. The
sampled ECHO record demonstrates the risk: `poly_DateCurrent` was
2026-10-21T19:38:43Z but `poly_PolygonDateTime` was
2026-06-21T15:43:27Z. A freshness age based only on the edit time would make an
old perimeter appear current.

ArcGIS JSON dates are signed epoch milliseconds in UTC. For example,
`1782016448000` is 2026-06-21T04:34:08Z. Normalize non-null dates to ISO 8601
UTC with a `Z` suffix.

## Observed values and quirks

At the observation time, Current returned 115 features and YearToDate returned
8,040. The Hub pages and services update continuously, so tests must not assert
these counts.

- YearToDate incident categories were 7,814 `WF` and 226 `RX`; all sampled
  `attr_IncidentTypeKind` values grouped as `FI`. Category, not kind, separates
  wildfire from prescribed fire.
- Names are not unique. The largest sampled duplicate groups included Bear
  (10), Cedar (8), Cherry (8), Cottonwood (8), and Airport (7). Bear records had
  distinct polygon IRWIN IDs. Exact-name lookup must return candidates when
  state still does not disambiguate.
- Names can differ only in case or formatting between polygon and incident
  fields (`Spout Springs` versus `SPOUT SPRINGS`). Search should be
  case-insensitive; display should prefer the incident name.
- `attr_POOState` uses values such as `US-CA` and `US-WY`, not bare postal
  codes.
- Nulls are common. In YearToDate, observed null counts were:
  `poly_Acres_AutoCalc` 1, `poly_GISAcres` 657, `attr_IncidentSize` 116,
  `attr_FinalAcres` 7,425, `attr_PercentContained` 6,212,
  `attr_IrwinID` 2,907, and `poly_DateCurrent` 1,819.
  `attr_FireDiscoveryDateTime` and `attr_POOCounty` had no nulls in this
  snapshot, but the normalizer must still accept them.
- Polygon linkage is more complete than joined attribution linkage. Prefer
  `poly_IRWINID`; sampled records had a polygon IRWIN ID while `attr_IrwinID`
  was null.
- Complexes require care. Twenty-nine observed records were marked
  `attr_IsCpxChild=1` with a non-null `attr_CpxID`. Parent and child perimeters
  can overlap, so summing acres is not guaranteed to equal unique land burned.
- A perimeter is an estimate and may contain unburned islands. Aggregated
  perimeter acres must not be phrased as a definitive amount "burned."
- Current membership is not a definitive real-time fire status. Fall-off rules
  also remove stale records, and data changes can lag source conditions.

## Schema inventory

Current has 119 fields and YearToDate has 120. Aliases currently equal field
names for every field. The 118 shared fields are grouped by ArcGIS type below.

| ArcGIS type | Shared field names |
| --- | --- |
| OID | `OBJECTID` |
| GlobalID | `GlobalID` |
| Integer | `poly_SourceOID`, `attr_SourceOID`, `attr_TotalIncidentPersonnel` |
| SmallInteger | `attr_IsFireCauseInvestigated`, `attr_IsFireCodeRequested`, `attr_IsFSAssisted`, `attr_IsMultiJurisdictional`, `attr_IsReimbursable`, `attr_IsTrespass`, `attr_IsUnifiedCommand`, `attr_POOLegalDescSection`, `attr_IsCpxChild`, `attr_FireStrategyConfinePercent`, `attr_FireStrategyFullSuppPrcnt`, `attr_FireStrategyMonitorPercent`, `attr_FireStrategyPointZonePrcnt` |
| Double | `poly_GISAcres`, `poly_Acres_AutoCalc`, `attr_CalculatedAcres`, `attr_IncidentSize`, `attr_DiscoveryAcres`, `attr_EstimatedCostToDate`, `attr_FinalAcres`, `attr_InitialLatitude`, `attr_InitialLongitude`, `attr_InitialResponseAcres`, `attr_PercentContained`, `attr_PercentPerimToBeContained`, `attr_EstimatedFinalCost`, `Shape__Area`, `Shape__Length` |
| Date | `poly_CreateDate`, `poly_DateCurrent`, `poly_PolygonDateTime`, `attr_ContainmentDateTime`, `attr_ControlDateTime`, `attr_FFReportApprovedDate`, `attr_FireDiscoveryDateTime`, `attr_FireOutDateTime`, `attr_ICS209ReportDateTime`, `attr_ICS209RptForTimePeriodFrom`, `attr_ICS209RptForTimePeriodTo`, `attr_InitialResponseDateTime`, `attr_StratDecisionPublishDate`, `attr_CreatedOnDateTime_dt`, `attr_ModifiedOnDateTime_dt` |
| String | `poly_IncidentName`, `poly_FeatureCategory`, `poly_MapMethod`, `poly_DeleteThis`, `poly_FeatureAccess`, `poly_FeatureStatus`, `poly_IsVisible`, `poly_IRWINID`, `poly_FORID`, `poly_SourceGlobalID`, `poly_Source`, `attr_ABCDMisc`, `attr_ADSPermissionState`, `attr_CreatedBySystem`, `attr_DispatchCenterID`, `attr_FFReportApprovedByTitle`, `attr_FFReportApprovedByUnit`, `attr_FireBehaviorGeneral`, `attr_FireBehaviorGeneral1`, `attr_FireBehaviorGeneral2`, `attr_FireBehaviorGeneral3`, `attr_FireCause`, `attr_FireCauseGeneral`, `attr_FireCauseSpecific`, `attr_FireCode`, `attr_FireDepartmentID`, `attr_FireMgmtComplexity`, `attr_FSJobCode`, `attr_FSOverrideCode`, `attr_GACC`, `attr_ICS209ReportStatus`, `attr_IncidentManagementOrg`, `attr_IncidentName`, `attr_IncidentShortDescription`, `attr_IncidentTypeCategory`, `attr_IncidentTypeKind`, `attr_IrwinID`, `attr_LocalIncidentIdentifier`, `attr_ModifiedBySystem`, `attr_POOCity`, `attr_POOCounty`, `attr_POODispatchCenterID`, `attr_POOFips`, `attr_POOJurisdictionalAgency`, `attr_POOJurisdictionalUnit`, `attr_POOJurisdictUnitParentUnit`, `attr_POOLandownerCategory`, `attr_POOLandownerKind`, `attr_POOLegalDescPrincipalMerid`, `attr_POOLegalDescQtr`, `attr_POOLegalDescQtrQtr`, `attr_POOLegalDescRange`, `attr_POOLegalDescTownship`, `attr_POOPredictiveServiceAreaID`, `attr_POOProtectingAgency`, `attr_POOProtectingUnit`, `attr_POOState`, `attr_PredominantFuelGroup`, `attr_PredominantFuelModel`, `attr_PrimaryFuelModel`, `attr_SecondaryFuelModel`, `attr_UniqueFireIdentifier`, `attr_FORID`, `attr_WFDSSDecisionStatus`, `attr_OrganizationalAssessment`, `attr_Source`, `attr_CpxName`, `attr_CpxID`, `attr_SourceGlobalID`, `attr_IncidentComplexityLevel` |

Dataset-specific fields:

| Dataset | Field | Type | Alias |
| --- | --- | --- | --- |
| Current only | `attr_ActiveFireCandidate` | SmallInteger | `attr_ActiveFireCandidate` |
| YearToDate only | `attr_IsQuarantined` | SmallInteger | `attr_IsQuarantined` |
| YearToDate only | `attr_IsValid` | SmallInteger | `attr_IsValid` |

The server must request explicit fields rather than `outFields=*`, and treat
dataset-specific fields as optional.

## Design consequences for the pilot

1. Use `poly_IRWINID` as the primary cross-dataset key and retain the Incident
   Locations join as a future `irwin_id`-keyed enrichment point.
2. Return both perimeter acres and its source. Detailed results may also expose
   reported/final incident acres under distinct names.
3. Compute perimeter age from polygon capture time and disclose when a fallback
   timestamp was required.
4. Normalize user state input to two uppercase letters and translate it to/from
   the upstream `US-XX` representation.
5. Use upstream statistics for simple groups, but include a warning on acreage
   totals because complex relationships and overlapping polygons can double
   count area.
6. Use an envelope/distance prefilter upstream, then fetch candidate geometry
   and calculate point-in-polygon, nearest edge, distance, and bearing locally.
   A centroid is not sufficient for proximity.
7. Do not infer containment from Current membership or from a null percent.
8. Cache for five minutes by default, but derive `data_as_of` from fetch time
   and report the latest observed perimeter capture timestamp separately.
9. Keep query construction internal and allowlist fields, operators, sort keys,
   and statistics. User input must never be interpolated as a raw ArcGIS
   `where` clause.
10. Every response needs the safety caveat: perimeters can lag ground
    conditions by a day or more, are not evacuation guidance, and users should
    consult local emergency officials and InciWeb at
    https://inciweb.wildfire.gov.