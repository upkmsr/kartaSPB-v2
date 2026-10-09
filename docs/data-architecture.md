# Data architecture

The long-term PostGIS layout is divided into schemas with explicit responsibilities:

| Schema | Responsibility |
| --- | --- |
| `meta` | Dataset registry, provenance, versions, and import runs |
| `staging` | Raw, source-shaped imported records with minimal transformation |
| `derived` | Source-specific geometry assembly and normalized relation structure |
| `catalog` | Canonical provider-independent GIS objects |
| `domain` | Specialised application models derived from canonical objects |
| `user` | User-owned places, preferences, and saved analyses |
| `analytics` | Grids, computed features, and scoring outputs |
| `upi` | Immutable official-source evidence snapshots, source-faithful normalized features, source profiles, and health observations |

FOUNDATION 1 uses `meta` and `staging`. FOUNDATION 2 adds `derived`; FOUNDATION
3A adds the canonical `catalog` core; 3B adds catalog category assignments and
their source/rule provenance. The domain schema remains empty.

UPI-A adds `upi` as a separate evidence boundary. It reuses global source identity in
`meta.dataset_sources` and run lifecycle in `meta.import_runs`; it does not feed
`catalog`, categories or domain models. `upi.source_snapshots`,
`upi.normalized_features`, and `upi.source_health` are append-only. The complete
contract, transactional failure behavior and retention gate are documented in
[upi-source-foundation.md](upi-source-foundation.md).

F6 activates the existing `analytics` boundary with
`analytics.analysis_cells`. It stores deterministic versioned square grids in both
EPSG:32636 (analysis) and EPSG:4326 (display), linked to stable district UUIDs. The
accepted production overview is 200 m; F10-R2 proves a 50 m detailed target and a 100 m
intermediate grid in isolation. Grid version and coordinates are part of stable cell
identity, so resolutions never reuse IDs. It does not store catalog objects, source
evidence, metrics, scores, or user state. See [analysis-grid.md](analysis-grid.md) and
[multi-resolution-analysis.md](multi-resolution-analysis.md).

F7 adds immutable metric runs and raw cell values plus an atomic mutable current pointer.
Definitions remain declarative and providers remain separate from persistence. Production
contains no real metric definitions in F7. F8 publishes the twelve accepted catalog-derived
raw metrics, and F9 publishes versioned normalized scores while calculating explicit-weight
composites on demand. See [metric-engine.md](metric-engine.md),
[existing-data-metrics.md](existing-data-metrics.md), and
[scoring-engine.md](scoring-engine.md).

F10 adds no table or persisted composite. It resolves a requested weight map and
`grid_version` to exact
immutable F9 score runs, encodes that historical plan in a bounded opaque spec, and serves
spatial-first MVT tiles. This keeps delivery and MapLibre rendering outside the canonical,
domain, and publication schemas. Existing F6–F9 keys already support multiple grid
versions; no F10-R2 migration is needed. Color contrast is a frontend-only paint transform
and is deliberately separate from both stored scores and grid resolution. See
[heatmap.md](heatmap.md).

F11A also persists no composite or user preference. Eight smooth-accessibility metrics
reuse the F8 immutable raw-run and F9 immutable normalized-run contracts; the Scenario
Builder sends explicit weights and receives the existing immutable heatmap plan. District
relative contrast is a read-only percentile query over the selected district cells. See
[smooth-accessibility.md](smooth-accessibility.md) and
[scenario-builder.md](scenario-builder.md).

## Source registry

`meta.dataset_sources` records stable identity and provenance: name, provider, type, URL, licence, attribution, provider version, SHA-256, local filename, download time, and upstream modification time. OSM values originate in `config/osm/source.json`, not Python constants.

## Import runs

`meta.import_runs` records each attempt to process a registered source. It includes lifecycle timestamps, source version and checksum, processing counters, JSONB details, and one of four statuses: `pending`, `running`, `success`, or `failed`.

The import run is operational metadata, not a source-specific domain table. Future adapters will all report through this common contract.

## OSM staging

The permanent tables are:

| Table | Identity and contents |
| --- | --- |
| `staging.osm_nodes` | `(source_id, osm_id)`, `osm_type=node`, all tags JSONB, point geometry |
| `staging.osm_ways` | `(source_id, osm_id)`, `osm_type=way`, all tags JSONB, line or polygon geometry |
| `staging.osm_relations` | `(source_id, osm_id)`, `osm_type=relation`, all tags JSONB; geometry may be null |
| `staging.osm_relation_members` | source/relation/sequence identity plus member type, ID, and role |

The explicit unique identity also includes `(osm_type, osm_id, source_id)`. Geometry columns use EPSG:4326 and GiST indexes; relation-member lookup and import-run columns have B-tree indexes. Temporary underscore-prefixed Flex tables are merged transactionally and removed after every handled success or failure.

Untagged nodes are geometry vertices used internally by osm2pgsql and are not retained as independent staging rows. Tagged nodes retain their OSM ID, full tag set, and coordinates. Ways and relations are not category-filtered.

The initial import is a full PBF load. Future incremental support can apply Geofabrik `.osc.gz` replication files to an update-capable staging workflow; FOUNDATION 1 does not implement replication.

## OSM derived geometry

`derived.osm_relation_geometries` contains the GIS interpretation of OSM
relations, never application categories. Its source identity is
`(source_id, relation_id)` and every row records the relation type, geometry
kind, assembly method, status, diagnostics, import run, and EPSG:4326 geometry.

- `multipolygon` and `boundary` areas are assembled by osm2pgsql/libosmium.
- `route` linework is collected from path way members and topologically merged
  with PostGIS; platform ways are deliberately excluded from the path geometry.
  Traversal order and duplicates remain available in `osm_route_members`.
- `assembled`, `partial`, `incomplete`, `invalid`, and `unsupported_nested`
  are explicit outcomes. A null geometry is never treated as success.

`derived.osm_route_members` resolves ordered route members as stop positions,
platforms, path ways, or other relations while retaining the original OSM
sequence, role, identity, tags, and geometry. `derived.osm_route_variants`
resolves `route_master` membership when such superrelations are present in the
extract.

No school, pharmacy, park, road, or transport application category is created
in this layer. Those meanings belong to FOUNDATION 3B.

## Canonical GIS core

`catalog.objects` owns stable, provider-independent UUIDs, canonical geometry,
name, lifecycle, revision, and field provenance. `catalog.object_sources`
binds each external identity to exactly one canonical UUID through the unique
key `(source_id, source_object_type, source_object_id)`. Candidate geometry and
name remain attributable to that binding; raw provider payloads stay in
`staging`.

Canonicalization is explicit and conservative:

- valid non-empty nodes and ways become generic `feature` objects;
- only `assembled` multipolygon and boundary relations are eligible;
- administrative boundaries use canonical kind `boundary`;
- routes and route masters never become generic catalog features;
- a new source identity creates a new UUID, with no name, distance, or overlap
  matching;
- unchanged payloads update observation provenance but not canonical revision;
- bbox absence never deletes or retires an object.

`catalog.relationships` stores directed, unordered relationships with source
provenance. It is not a transport member table. Ordered route members and route
variants remain in `derived.osm_route_members` and
`derived.osm_route_variants`.

Geometry selection is deterministic rather than last-write-wins: an explicit
lock wins, followed by source priority, geometry quality, latest successful
observation, and stable binding ID. The winning binding is recorded in
`geometry_source_id`; `name_source_id` and `property_sources` provide the same
provenance boundary for other canonical values.

## Schema management

Alembic is the sole production schema-management mechanism. Revision
`20260922_0002` creates OSM staging; revision `20260923_0003` creates the
derived relation-geometry layer; revision `20260924_0004` creates the canonical
GIS core; revision `20260924_0005` creates category persistence. Runtime
application code never calls `create_all()`. Revision `20261003_0011` adds only the
separate UPI source-evidence schema; applying it to production requires its own explicit
rollout authorization.

Revision `20261004_0012` adds only the F6 analysis-cell table and indexes. Cell creation
is an explicit, transactional bootstrap after migration; the migration itself performs
no data generation.

Revision `20261004_0013` adds the three F7 metric publication tables and append-only
guards. It contains no metric definitions and performs no metric calculation or data
bootstrap.

Revision `20261005_0014` adds the three universal F9 normalized-score publication tables
and append-only history guards. Normalization definitions remain versioned configuration,
not columns on the F8 raw metric contract. Combined explicit-weight scores are calculated
on demand and are not persisted. The authorized production rollout applied 0014 and
published twelve current normalized runs covering all 36,292 analysis cells; F8 raw metric
history and existing catalog/domain/UPI data remained unchanged.

F10 and F10-R2 require no Alembic revision. Their prepare response and tile spec are
stateless; existing F8/F9 immutable rows remain the only analytical inputs and user
scenarios remain deferred to F11. Parameterized grid generation is application code, not
schema mutation; production publication of another grid remains an explicit data rollout.

Revision `20261008_0015` adds exactly one concurrent covering index on
`analytics.analysis_cells (grid_version, district_id, cell_id)`. It closes the access-path
gap for bounded district distribution and contains no table rewrite, data publication,
trigger, column, constraint, or metric row. Its upgrade and downgrade deliberately run
outside Alembic's normal transaction by using an autocommit block for PostgreSQL
`CREATE/DROP INDEX CONCURRENTLY`.
# Category Engine (FOUNDATION 3B)

The canonical catalog remains provider-independent. Category definitions live in
`config/categories/taxonomy.json`; OSM mappings live separately in
`config/categories/sources/osm.json`. Rules use a deliberately small DSL
(`equals`, `in`, `exists`, `not_equals`, `not_in`) plus source-object, geometry-family,
and canonical-kind constraints. There is no executable expression support.

The full flow is `source -> staging -> derived -> canonical catalog -> category engine
-> API/domain`. The category engine never creates canonical objects. A batch orchestrator
may discover candidates from the same rules and pass their identities to the existing
canonicalization service before classification.

`catalog.object_categories` is the effective many-to-many classification.
`catalog.object_category_sources` records each supporting source binding, stable rule
ID/version, matched tag values, and observation runs. Reconciliation is limited to
bindings processed in the current scope; absence from a partial import never removes
evidence belonging to an unobserved binding. Routes and route masters remain transport
semantics and are not generic catalog places.

Raw OSM tags stay in staging. Canonical identity uses exact source identity without fuzzy
merge, and category evidence stores only matched fields plus stable rule identity/version.

## District domain registry

`domain.districts` is the authoritative application registry for the 18 Saint Petersburg
districts. It is intentionally narrower than the generic `boundary.administrative`
category. Its UUID is the stable public district identity; `canonical_object_id` is a
rebindable reference to the current GIS object. Names, slugs, display order, OSM relation
IDs, and frontend positions are not identities.

The registry does not duplicate geometry. Exact spatial truth is read through
`domain.districts -> catalog.objects.geom`. The idempotent district bootstrap validates
root relation `337422`, its 18 `role=subarea` level-5 relations, active exact OSM source
bindings, and valid non-empty SRID 4326 canonical geometry before writing any registry
rows. The committed deterministic district UUIDs remain unchanged if a future source
rebinding changes `canonical_object_id`.
