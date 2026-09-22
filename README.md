# KARTASPB v2

KARTASPB v2 is a desktop-only, data-driven GIS platform for analysing how convenient places in Saint Petersburg and the Leningrad Region are for living. It is not a property listing, mortgage, or residential-complex catalogue.

This repository is a clean FOUNDATION 0 implementation. No real datasets are imported yet. The former `upkmsr/kartaSPB` project remains a reference implementation and is not modified by this repository.

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

## Checks

```bash
docker compose exec backend pytest
docker compose exec backend ruff check app tests
docker compose exec backend mypy app

docker compose run --rm frontend-build npm test -- --run
docker compose run --rm frontend-build npm run lint
docker compose run --rm frontend-build npm run typecheck
docker compose run --rm frontend-build npm run build
```

See [development.md](docs/development.md) for host-based commands, integration test configuration, and the clean-database acceptance procedure.
