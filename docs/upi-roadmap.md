# UPI implementation roadmap proposal

UPI-1 discovery is complete. The project owner selected UPI as the active roadmap block;
the sequence below groups the capability matrix into seven coherent stages. It is not
authorization to start any stage beyond the explicitly accepted UPI-A slice.

## Roadmap decision gate

**F6 contract is not present in the repository. UPI is the active block; F6 remains
unstarted and deferred until its authoritative contract is supplied and reconciled.**

This decision does not delete or replace F6. UPI-B is not authorized by completion of
UPI-A.

## Proposed domain model

| Entity | Purpose | Stable identity | Temporal behavior | Geometry | Source linkage |
|---|---|---|---|---|---|
| `source_registry` | Approved source, authority, access, terms and health policy | internal source key | versioned configuration | none | one row per data product/adapter, not merely hostname |
| `source_snapshot` | Immutable raw retrieval/evidence envelope | source + retrieval/run ID + checksum | append-only | raw payload may contain geometry | URL/request, status, headers, checksum, retrieved-at |
| `normalized_feature` | Source-faithful comparable row | source + source object ID + source version | valid/observed intervals; never overwritten silently | source geometry plus normalized SRID | snapshot and raw locator |
| `change_event` | Explainable add/change/remove/status transition | deterministic source + object + before/after snapshot | event time and observation time | optional before/after geometry refs | exact evidence snapshots and diff fields |
| `planning_document` | Legal/admin document metadata | issuer + document number + date/version | amendments, supersession, validity | optional official footprint | official URL/file/checksum and related features |
| `development_site` | KARTASPB logical site spanning partial evidence | internal UUID, conservative merge policy | lifecycle state derived from evidence | explicit representative/site geometry | many evidence nodes; never replaces source IDs |
| `development_event` | Stage-specific event for a site | site + evidence event + type | ordered by effective/observed dates | optional event geometry | one or more `source_evidence` edges |
| `source_evidence` | Provenance graph edge and join method | internal edge ID | append-only/correctable | optional spatial relation evidence | `DIRECT_ID`, `SPATIAL`, `ADDRESS_ONLY`, `UNKNOWN` |
| `source_health` | Probe/schema/freshness observations | source + check time | time series | none | source registry, endpoint and probe result |

These are prospective entities only. They must not be added to the existing canonical
OSM catalog: official planning facts, evidence and temporal events are a separate domain.

## Generic source pipeline

```text
source adapter
    -> immutable raw snapshot
    -> source-faithful normalized snapshot
    -> typed attribute/status/geometry diff
    -> evidence-backed change events
    -> derived current state and development timeline
```

Rules:

1. Raw snapshots preserve request, response metadata, payload checksum and retrieval time.
2. Normalization never discards the source ID, document number, original value or CRS.
3. Diff compares like source versions: exact attributes and status, and canonicalized
   geometry with an explicit tolerance/method.
4. Events link both before/after evidence. “Missing” becomes removal only after source-
   specific completeness and retry rules pass.
5. Derived current state is rebuildable and labels inference separately from official fact.

## P0/P1 snapshot and diff units

| Source | Raw snapshot unit | Stable identity | Diffable fields | Geometry comparison | Status comparison |
|---|---|---|---|---|---|
| TORIS construction | paged ArcGIS layer/table response plus service metadata | GUID/ROOTID; permit ROOTID/document number | address, cadastral number, purpose, dates, parent keys | normalized EPSG:4326/3857 geometry hash plus topological equality | `STATUSOBJECT`, `STATUSDOCUMENT` |
| GIS Torgi | filtered page set and query contract | composite lot ID, notice + lot number | dates, category, price, attributes, cadastral/address values | only when sanctioned coordinates/geometry are validated | `lotStatus`, stop/annul flags |
| KGA layer registry | complete small JSON response | layer ID | name, visibility/access/export flags, scale, product generation | no feature diff; optional raster checksum is diagnostic only | layer presence/product version |
| KGA General Plan/PZZ WMS | named layer + exact request + underlying act version | layer ID + legal version | no trustworthy per-feature attributes | imagery comparison only; not semantic geometry diff | underlying legal act event |
| KGA DPT/AGO | layer registry plus linked legal document | layer/order/decision ID when available | document date/status/identifier | vector only after sanctioned extract; otherwise no semantic diff | document event |
| KIO publications | page/document and attachments | notice/document ID + date | parcel/address, auction date, use, price, outcome | cadastral join after approved geometry source | publication/outcome |

## Implementation stages

### UPI-A — source foundation and evidence safety

**Implementation/rehearsal status: complete on 2026-10-03; production rollout not
applied or authorized.** The accepted vertical slice is the TORIS construction polygon
layer with a bounded live probe and complete deterministic-fixture rehearsal. See
[upi-source-foundation.md](upi-source-foundation.md).

- Included work packages: source registry, immutable raw snapshots, normalized snapshot
  envelope, provenance, source health, schema contracts, licensing/access gates,
  incremental refresh primitives and idempotent adapter runs.
- Dependencies: roadmap/F6 order decision; legal/terms decision for first sources; backup
  and operational runbook standards.
- First visible value: internal source health/evidence inspection, not a public map layer.
- DB/API/frontend implications: new separate UPI schemas/tables and admin-only inspection;
  no changes to canonical identity; frontend optional.
- Main risk: building a generic framework before one real source proves the interfaces.
  Mitigation: vertical slice with TORIS metadata/count plus one small normalized layer.

### UPI-B — official planning layers

- Included work packages: General Plan, PZZ, KRT, height/protection/flood, official
  planning-layer provenance, legend/opacity, spatial source adapters and first map layers.
- Dependencies: UPI-A; supported KGA delivery/terms; S7 WMS or controlled-tile decision;
  legal version labels.
- First visible value: official functional-zoning and PZZ context on the map.
- DB/API/frontend implications: source-version metadata, raster/tile proxy or cache,
  Layer Registry entries, provenance panel; no catalog merge.
- Main risk: presenting GIS pixels as normative truth. Every layer must link the act,
  effective version, retrieval time and official-GIS classification.

### UPI-C — snapshots, diffs and change events

- Included work packages: historical snapshots, typed diff, geometry evolution, change
  feed, data-quality monitoring, incremental refresh and source-specific deletion rules.
- Dependencies: two stable UPI-A adapters and retained raw history.
- First visible value: verified “what changed” feed for selected official sources.
- DB/API/frontend implications: snapshot/diff/event tables, event API, time metadata and
  first simple timeline/compare controls.
- Main risk: false removals/schema drift. Completeness gates and quarantined changes are
  mandatory before publishing events.

### UPI-D — development intelligence

- Included work packages: land activity, planning documents, AGO, permits,
  commissioning, construction status, development sites/events, stage engine evidence,
  dormant/cancelled handling, timeline and evidence graph.
- Dependencies: UPI-A/C; TORIS/GIS Torgi semantic contracts; authorized GPZU/AGO/PPT
  evidence where available; conservative identity policy.
- First visible value: “Перспективные участки” with evidence-backed stage and chronology.
- DB/API/frontend implications: site/event/evidence domain, search and filters, site card,
  event timeline; source facts remain inspectable.
- Main risk: false merges. Direct IDs outrank spatial/address joins; uncertain evidence
  must stay separate or explicitly probabilistic.

### UPI-E — planning context, height and industrial transformation

- Included work packages: parcel↔zoning/protection/KRT intersections, planning context
  card, height intelligence, industrial/grey-belt classification, spatial intersection,
  industrial transformation and future-infrastructure context.
- Dependencies: lawful parcel geometry or scoped alternatives; UPI-B/D source versions;
  documented analytical definitions.
- First visible value: explainable site context (“zone, constraints, planned network,
  industrial/KRT evidence”) with source dates.
- DB/API/frontend implications: versioned intersection results, analysis API, context
  sections and filters.
- Main risk: computed intersections being mistaken for administrative decisions. Mark all
  relations `derived`, show method and input versions.

### UPI-F — time, comparison and evidence UX

- Included work packages: time UI, historical map, compare mode, change feed refinement,
  development timeline, evidence drill-down, combined analysis and source freshness UX.
- Dependencies: meaningful retained history from UPI-C and events from UPI-D.
- First visible value: select a date/range, compare states, and open primary evidence.
- DB/API/frontend implications: temporal query APIs, cache strategy, time controls,
  before/after rendering and accessible evidence views.
- Main risk: apparent precision beyond observation cadence. UI must distinguish effective,
  publication and first-observed dates.

### UPI-G — advanced climate, viewshed and 3D foundation

- Included work packages: wind/climate, environmental context, official dominants,
  derived viewsheds, infrastructure impact, 3D/height foundation and advanced combined
  analysis.
- Dependencies: official observation/licensing research, validated height inputs,
  methodology review and sufficient compute budget.
- First visible value: clearly labeled analytical overlays with uncertainty and source
  provenance.
- DB/API/frontend implications: raster/3D artifacts, model-run metadata, analysis tiles,
  adjustable legends and methodology panels.
- Main risk: derived models appearing official or predictive. Separate official inputs,
  model assumptions, run version and uncertainty at every API/UI boundary.

## Suggested first implementation slice after authorization

The safest vertical slice is **TORIS construction service metadata + one paged object
adapter + evidence snapshot + non-production inspection**, because it has stable IDs,
structured status, geometry, document tables and a bounded count baseline. The first
public visual layer can then be either this normalized construction layer or the lower-
interaction KGA General Plan raster, depending on the source-terms/S7 transport decision.

This recommendation deliberately separates:

- first engineering proof: TORIS structured evidence;
- first simple official visual demo: KGA General Plan/PZZ WMS;
- first development-intelligence feed: GIS Torgi + TORIS events;
- advanced analysis: later derived climate/viewshed/impact work.

## Exit criteria before coding

1. Roadmap owner resolves UPI versus F6 ordering.
2. First source has written authority/terms, rate and retention decision.
3. Raw evidence retention and deletion policy is approved.
4. S7 delivery decision resolves WMS/version metadata gaps if KGA is first visual layer.
5. A representative source contract fixture and failure/recovery plan are specified.
6. Production DB migration/import/cutover is a separate authorized task.
