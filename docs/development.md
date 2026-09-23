# Development

## Docker workflow

Copy `.env.example` to `.env`, then start the complete stack:

```bash
docker compose up --build --wait
```

Compose waits for PostgreSQL, runs Alembic to completion, then starts the API and frontend. Readiness requires a database connection, a working PostGIS function, and an Alembic revision matching the code's current head.

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
```

Handled PBF validation, Osmium, osm2pgsql, and merge errors finish the current import run as `failed`. A database outage is reported directly because no database is available in which to persist telemetry. Source and extract `.part` files are removed on interrupted or failed operations.

## Clean-database acceptance

This deliberately removes the local KARTASPB v2 database volume:

```bash
docker compose down -v
docker compose up --build --wait
curl --fail http://localhost:8000/api/health/live
curl --fail http://localhost:8000/api/health/ready
```

Verify failure and recovery behaviour:

```bash
docker compose stop db
curl --fail http://localhost:8000/api/health/ready # expected to fail
docker compose start db
docker compose up --wait
curl --fail http://localhost:8000/api/health/ready
```

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
