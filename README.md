# KARTASPB v2

KARTASPB v2 is a desktop-only, data-driven GIS platform for analysing how convenient places in Saint Petersburg and the Leningrad Region are for living. It is not a property listing, mortgage, or residential-complex catalogue.

FOUNDATION 1 adds a source-oriented OpenStreetMap ingestion engine. It downloads a provider PBF safely, creates configured geographic extracts with Osmium, imports complete raw tags and OSM identity through osm2pgsql Flex, and stops at PostGIS `staging`. The former `upkmsr/kartaSPB` project remains a reference implementation and is not modified by this repository.

## Architecture

External open data flows through source adapters, staging, normalisation, and a canonical GIS model before it reaches domain logic, the API, and the frontend. This keeps the application independent of any one provider.

The target UI is a desktop web application for mouse, keyboard, and a large map viewport. The minimum supported width is 1280 px; phone and tablet layouts are intentionally outside scope.

Read [architecture.md](docs/architecture.md), [data-architecture.md](docs/data-architecture.md), and [data-sources.md](docs/data-sources.md) for the design boundaries.

## Quick start

Requirements: Docker with Docker Compose.

```bash
cp .env.example .env
docker compose up --build --wait
```

The example password is suitable only for local development. Change it before exposing any service.

Open:

- Frontend: <http://localhost:5173>
- Backend API: <http://localhost:8000>
- OpenAPI documentation: <http://localhost:8000/docs>
- Liveness: <http://localhost:8000/api/health/live>
- Readiness: <http://localhost:8000/api/health/ready>

Stop services while retaining the database:

```bash
docker compose down
```

Remove the local database volume as well:

```bash
docker compose down -v
```

## Migrations

Migrations run automatically before the backend starts. To run them manually:

```bash
docker compose run --rm migration
```

Create future revisions from inside the backend image, then review generated SQL carefully:

```bash
docker compose run --rm migration alembic -c /app/alembic.ini revision --autogenerate -m "description"
```

Database objects are managed by Alembic. The application does not call `Base.metadata.create_all()`.

## OpenStreetMap ingestion

The tooling runs entirely in the Compose `ingest` service; no host installation of Osmium or osm2pgsql is required. Start the database and migrations first, then use this copy/paste workflow:

```bash
docker compose up -d db migration
docker compose run --rm ingest download
docker compose run --rm ingest extract --region spb_smoke
docker compose run --rm ingest import --region spb_smoke
docker compose run --rm ingest status
docker compose run --rm ingest inspect
```

The complete coarse target profile uses the same workflow:

```bash
docker compose run --rm ingest extract --region spb_lo
docker compose run --rm ingest import --region spb_lo
```

`download --force` explicitly checks for an upstream refresh; `extract --force` rebuilds an extract. Normal download and extract commands are checksum-idempotent. `spb_lo` is a geographic bounding box, not an official administrative boundary.

## Checks

```bash
docker compose exec backend pytest
docker compose exec backend ruff check app tests /migrations
docker compose exec backend mypy app

docker compose run --rm frontend-build npm test -- --run
docker compose run --rm frontend-build npm run lint
docker compose run --rm frontend-build npm run typecheck
docker compose run --rm frontend-build npm run build
```

See [development.md](docs/development.md) for host-based commands, integration test configuration, and the clean-database acceptance procedure.
