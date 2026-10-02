# Development

## Docker workflow

Copy `.env.example` to `.env`, then start the complete stack:

```bash
docker compose up --build --wait
```

Compose waits for PostgreSQL, runs Alembic to completion, then starts the API and frontend. Readiness requires a database connection, a working PostGIS function, and an Alembic revision matching the code's current head.

The database image is built from `db/Dockerfile`: the official multi-arch
PostgreSQL 17.5 Bookworm image plus the pinned PGDG PostGIS 3 package. Docker
must select an image matching the Docker VM architecture; do not add
`platform: linux/amd64` on an arm64 VM. Verify a running stack with:

```bash
make db-architecture
```

Database runtime migrations use logical `pg_dump`/`pg_restore` into a fresh
volume. Never attach an existing production PGDATA volume to a different
runtime image as an architecture-migration shortcut. The production procedure
and rollback boundary are documented in the
[native database cutover runbook](native-database-cutover.md).

The OSM tools are pinned in `ingest/Dockerfile`. Confirm the installed versions with:

```bash
docker compose run --rm ingest versions
```

## OSM workflow and inspection

```bash
docker compose run --rm ingest download
docker compose run --rm ingest extract --region spb_smoke
docker compose run --rm ingest import --region spb_smoke
docker compose run --rm ingest status
docker compose run --rm ingest inspect
```

Useful manual SQL:

```sql
SELECT osm_type, count(*) FROM (
  SELECT osm_type FROM staging.osm_nodes
  UNION ALL SELECT osm_type FROM staging.osm_ways
  UNION ALL SELECT osm_type FROM staging.osm_relations
) objects GROUP BY osm_type;

SELECT ST_GeometryType(geom), count(*) FROM (
  SELECT geom FROM staging.osm_nodes
  UNION ALL SELECT geom FROM staging.osm_ways
  UNION ALL SELECT geom FROM staging.osm_relations
) geometries WHERE geom IS NOT NULL GROUP BY 1;

SELECT * FROM meta.dataset_sources ORDER BY id;
SELECT * FROM meta.import_runs ORDER BY id DESC LIMIT 10;
SELECT osm_type, osm_id, tags FROM staging.osm_nodes WHERE tags @> '{"amenity":"school"}' LIMIT 5;
SELECT relation_id, sequence, member_type, member_id, role
FROM staging.osm_relation_members ORDER BY relation_id, sequence LIMIT 20;

SELECT relation_type, assembly_status, count(*)
FROM derived.osm_relation_geometries
GROUP BY relation_type, assembly_status ORDER BY relation_type, assembly_status;

SELECT relation_id, sequence, member_kind, member_type, member_id, role, is_resolved
FROM derived.osm_route_members
ORDER BY relation_id, sequence LIMIT 50;
```

Real `spb_smoke` FOUNDATION 2 acceptance IDs include:

| OSM relation | Expected interpretation |
| --- | --- |
| `1898904` | Water polygon with 14 holes assembled from split ways |
| `1920691` | Building MultiPolygon with two components |
| `1185383` | Valid administrative boundary polygon |
| `14363086` | Bus route with ordered stops, platforms, and path ways |
| `1942052` | Tram route |
| `969924` | Trolleybus route |
| `252537` | Subway route |
| `17983655` | Train route |

`route_master` and `route=light_rail` are absent from the current smoke
extract and must not be reported as synthetic passes. The registered
Northwestern source PBF does contain Saint Petersburg route masters: relation
`1735012` (`route_master=trolleybus`, ref `1`) resolves, in source order, to
route variants `969924` and `969270`. A reference-complete Osmium extract is
the acceptance path for this source-only case; it is not part of the committed
dataset.

Handled PBF validation, Osmium, osm2pgsql, and merge errors finish the current import run as `failed`. A database outage is reported directly because no database is available in which to persist telemetry. Source and extract `.part` files are removed on interrupted or failed operations.

## Clean-database acceptance

Use a distinct disposable project for clean-database acceptance. The alternate ports
avoid the normal development or production project, and `down -v` targets only this
explicit project:

```bash
POSTGRES_PORT=15436 BACKEND_PORT=18012 FRONTEND_PORT=15185 \
  docker compose -p kartaspb-native-ci up --build --wait
./scripts/check-db-architecture.sh kartaspb-native-ci-db-1
curl --fail http://localhost:18012/api/health/live
curl --fail http://localhost:18012/api/health/ready
```

Verify failure and recovery behaviour:

```bash
docker compose -p kartaspb-native-ci stop db
curl --fail http://localhost:18012/api/health/ready # expected to fail
docker compose -p kartaspb-native-ci start db
POSTGRES_PORT=15436 BACKEND_PORT=18012 FRONTEND_PORT=15185 \
  docker compose -p kartaspb-native-ci up --wait
curl --fail http://localhost:18012/api/health/ready
docker compose -p kartaspb-native-ci down -v
```

Never use `docker compose down -v` with the production project. Database runtime
migrations must preserve the old volume and restore a logical dump into a new volume.

## Backend on the host

Python 3.12 or newer is required.

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
ruff check app tests
mypy app
pytest -m 'not integration'
```

Database integration tests use `TEST_DATABASE_URL`, falling back to `DATABASE_URL`:

```bash
TEST_DATABASE_URL='postgresql+psycopg://kartaspb:change-me@localhost:5432/kartaspb' pytest -m integration
```

## Frontend on the host

Node.js 22 or newer is recommended.

```bash
cd frontend
npm ci
npm run lint
npm run typecheck
npm test -- --run
npm run build
npm run dev
```

Vite proxies `/api` to `http://localhost:8000` during development. A non-empty `VITE_API_BASE_URL` can override that base URL when required.

## Desktop scope

Only desktop browser QA at widths of 1280 px and above is required. Do not add phone/tablet layouts, touch-first controls, bottom sheets, or mobile-specific React components.
