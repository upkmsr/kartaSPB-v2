# UPI source gaps and integration constraints

This document records what was **not** established during UPI-1. A proposed approach is
design input only; no workaround is implemented here.

## Material source gaps

| Gap | Consequence | Later approach | Priority |
|---|---|---|---|
| KGA planning layers expose working WMS images but no verified WFS/vector export | No stable feature IDs, attributes or exact geometry diff | Ask KGA for sanctioned vector/open-data route; meanwhile use raster only with explicit attribution | P0 decision |
| KGA WMS proxy returns 204 for `GetCapabilities` | Standard capability discovery and cache rules cannot be inferred | Build only against documented/tested layer registry + `GetMap`, or obtain provider contract | P0 decision |
| GIS and NSPD sites present certificate-chain problems to the local client | Naive production clients would fail TLS validation | Provider/support escalation and trusted CA remediation; never ship `verify=false` | P0 operational |
| Public KGA layer dates are blank | Freshness cannot be proven from layer metadata | Snapshot registry response and retain retrieval time; use legal publication dates separately | P1 |
| No complete official machine historical archive was found | Cannot reconstruct prior maps merely from current endpoints | Start prospective snapshots; ingest archived legal acts only through versioned document adapters | P1 |
| GPZU is available through a paid/requested ISOGD service, not a public API | Citywide automatic early planning coverage is unavailable | Manual/authorized acquisition with explicit scope and terms, or defer | P2 |
| Public AGO layer has no verified decision ID/date schema | Cannot safely generate design-stage events | Join to official decision documents/requested extracts; do not infer from pixels | P1 |
| DPT/PPT/PMT layers lack verified stable feature IDs | Site history and object-level diff are fragile | Preserve layer/order document IDs and seek vector extracts; otherwise document-event model | P1 |
| TORIS service attribution/authority wording is not fully aligned | “Committee for Construction” credit must not be conflated with permit issuer | Confirm data owner and status semantics before product labels; retain document issuer per row | P0 legal/semantic |
| TORIS exposes current status but no proven revision history | State transitions before first snapshot may be lost | Prospective snapshots plus document dates; never fabricate earlier events | P1 |
| ESSK is an authenticated service workflow, not a proven public data API | Applicant states/documents cannot be treated as an open citywide feed | Pursue an official integration contract or keep it outside automated discovery | P3 |
| GIS Torgi public API is discoverable but not formally documented in the inspected sources | Endpoint stability, limits and reuse terms are uncertain | Seek official API terms; use throttled adapter with schema contract and circuit breaker | P0 operational |
| City auction pages are heterogeneous HTML/documents | Parser drift and duplicate notices likely | Treat GIS Torgi as primary machine feed; KIO pages as city authority corroboration | P1 |
| Parcel geometry has no approved automated source | Many cadastral joins cannot be spatially resolved at scale | Use cadastral numbers and authorized extracts first; add geometry only after terms review | P0 dependency |
| NSPD public map does not equal an EGRN extract | Public visualization could be mistaken for legal cadastral evidence | Label as context only and link evidence to official extract when required | Permanent rule |
| Saint Petersburg Open Data portal root returned 404 | Potential structured datasets could not be inventoried | Recheck via city operator/support; do not design dependencies on the dead root | P2 |
| InfoEco was unreachable through the inspected TLS path | Station schema, archive and update interval remain unverified | Provider follow-up; use official reports/manual seed until a supported endpoint exists | P2 |
| Climate normals found are for 1961–1990 and no wind-rose dataset/API was verified | Cannot claim current neighborhood wind climatology | Research Roshydromet data catalogue/licensing; otherwise show station observations only | P2 |
| No official citywide wind surface exists | Wind field would be a model, not an observation | `derived-analysis` with methodology, input stations, time window and uncertainty | P3 |
| Flood layer is present in PZZ GIS but public feature attributes are not exposed | Constraint meaning/version cannot be queried per polygon | Pair raster with current PZZ act, later acquire sanctioned vectors | P1 |
| “Grey belt” has no single authoritative official entity set | Overbroad analytical labels risk false authority | Define a documented derived classification from production zones/KRT/history | P2 |
| KRT polygons do not represent every redevelopment project | Incomplete development-site coverage | Treat KRT as one evidence type, not the development-site universe | Permanent rule |
| Named official dominant inventory was not established | Cannot build a definitive Saint Isaac's/Admiralty/etc. list | Manual seed only after a primary heritage/planning reference is found | P2 |
| No official computed protected viewshed was found | A visibility surface cannot be called official | Build only as `DERIVED_NOT_SOURCE`, preserving official restriction inputs | P3 |
| General Plan planned infrastructure lacks verified per-feature delivery dates/status | Planned networks could be read as committed construction | Label “General Plan planned”; do not infer funding or schedule | Permanent rule |
| Public-source licenses/terms are often unclear | Republishing vectors/tiles may be impermissible | Legal/terms review per source before caching, redistribution or bulk ingestion | P0 gate |

## Evidence graph join baseline

| Relationship | Best join discovered | Confidence | Rule |
|---|---|---|---|
| construction object ↔ permit | `GUID/ROOTID` to `PARENT_GUID/PARENT_ROOTID` in TORIS | `DIRECT_ID` | Preserve both source rows and document number |
| construction object ↔ commissioning | same TORIS parent keys | `DIRECT_ID` | Commissioning is an event, not object replacement |
| land lot ↔ parcel | cadastral number in lot attributes/name | `DIRECT_ID` when structured and valid; otherwise `ADDRESS_ONLY` | Normalize but retain raw value |
| parcel ↔ PPT/PMT | planning-document parcel layers / document references | `UNKNOWN` publicly | Do not claim direct linkage until vector attributes are obtained |
| parcel ↔ GPZU | cadastral identifier expected in official document | `DIRECT_ID` only in acquired document | Public bulk availability absent |
| parcel ↔ AGO | no public common ID proven | `SPATIAL` or `ADDRESS_ONLY` | Show join method and uncertainty |
| parcel ↔ permit | `KADASTRNUMBER` in TORIS when populated | `DIRECT_ID`; fallback `ADDRESS_ONLY` | Profile completeness before relying on it |
| parcel ↔ zoning | intersection with PZZ geometry | `SPATIAL` | Computed relation, record PZZ version |
| parcel ↔ height/protection | intersection with constraint geometry | `SPATIAL` | Computed relation, record rule/act version |
| parcel ↔ industrial/KRT | intersection with production/KRT polygons | `SPATIAL` | Never turn intersection into project status |
| project/site ↔ future infrastructure | proximity/intersection | `SPATIAL` | Derived impact with threshold/methodology |

There is no proven primary identifier spanning parcel → PPT/PMT → GPZU → AGO → permit →
construction. The future evidence graph must support partial chains and multiple candidate
joins rather than force a false one-to-one lifecycle.

## S7 contract mapping

| Source/product | `layerClass` | Source type | `loadingStrategy` | `loadParticipation` | `districtHandling` | Selection | Time | Legend/opacity | Provenance |
|---|---|---|---|---|---|---|---|---|---|
| KGA General Plan zones | `raster` | `raster-tile` after controlled proxy | `tiles` | `maplibre-native` | `ignored` or source-managed | `none` | `snapshot` metadata is currently invalid for raster contract, so external version metadata is needed | fill-like legend; adjustable opacity | `official` |
| KGA PZZ/constraints/KRT | `raster` | `raster-tile` after controlled proxy | `tiles` | `maplibre-native` | `ignored` | `none` | current snapshot outside layer time contract | categorical/line legends; adjustable | `official` |
| TORIS construction objects | `temporal-vector` | normalized `geojson` or vector tiles | `viewport`/`tiles` | `independent`/`maplibre-native` | `source-managed` | `layer-feature` by GUID | `event` or `range` | status point/fill; adjustable | `official` |
| GIS Torgi lots | `temporal-vector` | normalized `geojson` | `viewport` | `independent` | `source-managed` | `layer-feature` by lot ID | `event`/`range` | status/category point/fill; adjustable | `official` |
| DPT/AGO raster fallback | `raster` | `raster-tile` | `tiles` | `maplibre-native` | `ignored` | `none` | external snapshot metadata | planning/design legend | `official` |
| Future official vector extracts | `reference-vector` or `temporal-vector` | `geojson`/vector tiles | `static`/`tiles` | `independent` | `source-managed` | `layer-feature` | source-dependent | required | `official` |
| Computed viewshed/wind/impact | `derived-analysis` | derived GeoJSON/raster/vector tiles | `static`/`tiles` | `independent`/`maplibre-native` | `source-managed` | usually `none` | derived snapshot/range | method-specific; adjustable | `derived` |

### S7 gaps

The current contract fits all discovered transport/semantic classes, but two metadata
gaps must be resolved before implementation:

1. Raster/reference layers may need version/effective-date metadata while S7 restricts
   non-temporal classes to `time.kind="none"`. A source-level snapshot/version descriptor
   is needed without pretending the raster is a temporal feature layer.
2. WMS is not a native S7 source type. Production must either expose controlled raster
   tiles through an application adapter/cache or add a generic WMS driver in a later,
   explicitly reviewed contract change.

No S7 code is changed in UPI-1.

## Reliability baseline and gates

- KGA: layer registry and GetMap work; capabilities/vector/export do not. Gate: publisher
  terms, version labeling and a supported production delivery path.
- TORIS: REST metadata and count queries work with stable IDs. Gate: publisher/field
  semantics, terms, pagination and representative-record contract tests.
- GIS Torgi: public JSON search works. Gate: official API terms, SPb query/filter proof,
  cadence and rate-limit policy.
- RGIS: public shell and REST directory work; organizational cabinet requires ESIA.
  Gate: per-service authority and licensing.
- NSPD: public shell works only after local TLS diagnostic bypass. Gate: documented
  automated access and reuse rights.
- InfoEco/Open Data: unavailable or incomplete during probe. Gate: provider-supported
  endpoint; no scraper workaround should silently become production infrastructure.
