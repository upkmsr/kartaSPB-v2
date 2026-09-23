# Data architecture

The long-term PostGIS layout is divided into schemas with explicit responsibilities:

| Schema | Responsibility |
| --- | --- |
| `meta` | Dataset registry, provenance, versions, and import runs |
| `staging` | Raw, source-shaped imported records with minimal transformation |
| `catalog` | Canonical provider-independent GIS objects |
| `domain` | Specialised application models derived from canonical objects |
| `user` | User-owned places, preferences, and saved analyses |
| `analytics` | Grids, computed features, and scoring outputs |

FOUNDATION 1 uses `meta` and `staging`; canonical and domain schemas remain intentionally empty.

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

## Schema management

Alembic is the sole production schema-management mechanism. Revision `20260922_0002` extends source metadata and creates OSM staging. Runtime application code never calls `create_all()`.
