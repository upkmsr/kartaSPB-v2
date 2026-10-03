# UPI source evidence foundation

UPI-A introduces a source-faithful evidence boundary for Urban Project Intelligence.
It is operational infrastructure, not a public product layer and not an extension of the
OSM canonical catalog.

## Schema boundary

Global source identity remains in `meta.dataset_sources`; every UPI data product gets its
own row there. Execution lifecycle remains in `meta.import_runs`, including
`pending -> running -> success|failed` and the existing processing counters. UPI does not
create a competing source registry or run table.

Revision `20261003_0011` adds the dedicated `upi` schema:

| Table | Responsibility |
| --- | --- |
| `upi.source_profiles` | Adapter/configuration, authority, access, terms, retention and refresh policy for a registered dataset source |
| `upi.source_snapshots` | Immutable retrieval envelope, request metadata, schema fingerprint, checksum and optional policy-authorized raw evidence |
| `upi.normalized_features` | Immutable source-faithful features linked to source and snapshot, with stable source ID, normalization version, property whitelist and EPSG:4326 geometry |
| `upi.source_health` | Append-only health observations and structured failure classifications |

Each snapshot records the exact config, adapter and normalization versions used.
Database triggers reject `UPDATE` and `DELETE` on snapshots, normalized features and
health observations. A repeated successful retrieval always creates a new snapshot. The
new row is marked `UNCHANGED` when its deterministic payload checksum matches the prior
snapshot; no diff event is created in UPI-A.

The migration does not alter `catalog` or `domain`. UPI facts cannot silently become
canonical places, categories, facilities, streets or development-stage claims.

## Transaction and failure semantics

A write-capable run first creates an existing `meta.import_runs` row as `pending`, then
moves it to `running`. Source retrieval, schema validation and normalization must all
finish before publication. The snapshot, all normalized features, successful run state
and `CURRENT` health observation commit in one bounded database transaction.

If pagination, count validation, identity validation, schema validation, geometry
normalization or database persistence fails, that publication transaction rolls back.
The run is then recorded as `failed` and a separate append-only health observation
records `SOURCE_UNAVAILABLE`, `SCHEMA_CHANGED`, `PARTIALLY_UPDATED` or `IMPORT_FAILED`.
No incomplete snapshot can be reported as current.

## TORIS construction contract

The first profile is `toris-construction`, configured in
`config/upi/sources/toris_construction.json`. It targets only layer 3, “Объекты
жилищного строительства (контур)”, of the official Saint Petersburg TORIS/RGIS ArcGIS
MapServer. Permit, commissioning, ZOS, developer, marketing and other TORIS tables are
out of scope.

Live verification on 2026-10-03 found:

- `esriGeometryPolygon`, published in WKID 102100/latest WKID 3857;
- count 324, within the approved 200–600 order-of-magnitude guard;
- query output successfully transformed by the server to EPSG:4326;
- `supportsPagination=false`, so offset pagination is invalid for this layer;
- `returnIdsOnly` returns the complete `OBJECTID` set, which is fetched in sorted,
  bounded `objectIds` chunks;
- `GUID` is the stable source business identity; `OBJECTID` is only the deterministic
  transport cursor, while `ROOTID` remains preserved source evidence.

Every run requires count = unique returned OBJECTIDs = retrieved features = unique GUIDs.
Any mismatch fails closed. The explicit normalizer version is
`toris-construction-v1`.

The normalized property whitelist is limited to GUID, ROOTID, source row ID, address,
name, source status, source creation value, cadastral number and purpose. Unapproved
attributes are not copied into normalized properties. Official `STATUSOBJECT` is stored
verbatim; UPI-A does not infer a KARTASPB development stage.

## Geometry

The adapter requests `outSR=4326`. ArcGIS rings are converted with Shapely containment
and validity checks, independently of ring orientation, into valid GeoJSON Polygon or
MultiPolygon geometry. Empty, malformed, out-of-range or topologically invalid geometry
fails the run. PostGIS stores the result as SRID 4326 without simplification. The
snapshot request metadata retains the output CRS contract; source metadata retains the
published 102100/3857 extent.

## Schema fingerprint

The deterministic fingerprint covers geometry type, stable/business identity contract,
transport object-ID contract, output SRID and each configured field's name, source type,
nullability and required flag. Volatile descriptions and unconsumed optional fields are
excluded. Thus a new ignored optional source field is compatible, while removal or type
change of GUID/required fields, or an incompatible geometry type, is
`SCHEMA_CHANGED` and stops publication.

## Provenance trace

For every normalized feature the database can resolve:

```text
normalized feature
  -> source_object_id + normalization_version + payload_hash + raw_locator
  -> immutable source snapshot + payload checksum + retrieval/request metadata
  -> meta.import_runs execution and counters
  -> meta.dataset_sources global source identity
```

Fixture snapshots may retain their full deterministic fixture payload with a
`fixture://` locator. Live payload retention remains gated separately from endpoint
access.

## Terms and retention gate

The endpoint is public and unauthenticated, but the layer metadata has empty
`copyrightText` and no official reusable-data or persistent-retention grant was found.
The profile therefore remains:

- terms: `PUBLIC_BUT_TERMS_UNCLEAR`;
- raw retention: `METADATA_ONLY`;
- live raw payload retention: **not authorized**.

Only a bounded live metadata/count/OBJECTID/three-feature probe was used for UPI-A. The
complete ingestion rehearsal uses a committed deterministic fixture in a disposable
PostGIS database. The CLI refuses a live snapshot under this retention policy.

## CLI

Commands are manual and emit one JSON object:

```bash
python -m app.upi validate-config --source toris-construction
python -m app.upi probe --source toris-construction
python -m app.upi snapshot --source toris-construction \
  --fixture tests/fixtures/upi/toris_construction.json
```

`validate-config` and `probe` require no database and write no health or evidence rows.
`probe` reads metadata, count, the ID set and at most three full features. `snapshot` is
the explicit database-writing command; for TORIS in UPI-A it requires a deterministic
fixture. There is no scheduler, background poller, public API or frontend integration.

## Production rollout policy

UPI-A authorizes migration/code development and disposable rehearsal only. Production
must remain at Alembic `20261001_0010`; do not deploy a backend requiring 0011, create
the `upi` schema, or import TORIS data there without a separate production rollout
authorization. A future authorization must re-check terms/retention, backup and
invariants before applying 0011.
