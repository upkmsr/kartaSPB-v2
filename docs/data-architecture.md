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

FOUNDATION 0 creates the schemas to reserve these boundaries, but only adds tables in `meta`.

## Source registry

`meta.dataset_sources` records the stable identity and provenance of an external dataset: name, provider, type, URL, licence, and attribution. Future revisions may add version, checksum, download time, and upstream modification time when ingestion begins.

## Import runs

`meta.import_runs` records each attempt to process a registered source. It includes lifecycle timestamps, source version and checksum, processing counters, JSONB details, and one of four statuses: `pending`, `running`, `success`, or `failed`.

The import run is operational metadata, not a source-specific domain table. Future adapters will all report through this common contract.

## Schema management

Alembic is the sole production schema-management mechanism. The initial migration enables PostGIS, creates the six schemas, and creates the metadata tables. Runtime application code never calls `create_all()`.
