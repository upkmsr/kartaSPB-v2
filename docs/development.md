# Development

## Docker workflow

Copy `.env.example` to `.env`, then start the complete stack:

```bash
docker compose up --build --wait
```

Compose waits for PostgreSQL, runs Alembic to completion, then starts the API and frontend. Readiness requires a database connection, a working PostGIS function, and an Alembic revision matching the code's current head.

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
