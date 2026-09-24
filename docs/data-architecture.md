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

FOUNDATION 1 uses `meta` and `staging`. FOUNDATION 2 adds `derived`; canonical and
domain schemas remain intentionally empty.

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

No school, pharmacy, park, road, or transport application object is created in
this layer. Those meanings belong to the future canonical catalogue.

## Schema management

Alembic is the sole production schema-management mechanism. Revision
`20260922_0002` creates OSM staging; revision `20260923_0003` creates the
derived relation-geometry layer. Runtime application code never calls
`create_all()`.
