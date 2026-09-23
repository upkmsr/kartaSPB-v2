.PHONY: up down migrate backend-test backend-quality frontend-test frontend-quality check osm-download osm-smoke osm-import osm-status osm-inspect

up:
	docker compose up --build --wait

down:
	docker compose down

migrate:
	docker compose run --rm migration

backend-test:
	docker compose exec backend pytest

backend-quality:
	docker compose exec backend ruff check app tests
	docker compose exec backend mypy app

frontend-test:
	docker compose run --rm frontend-build npm test -- --run

frontend-quality:
	docker compose run --rm frontend-build npm run lint
	docker compose run --rm frontend-build npm run typecheck
	docker compose run --rm frontend-build npm run build

check: backend-quality backend-test frontend-quality frontend-test

osm-download:
	docker compose run --rm ingest download

osm-smoke:
	docker compose run --rm ingest smoke

osm-import:
	docker compose run --rm ingest import --region spb_lo

osm-status:
	docker compose run --rm ingest status

osm-inspect:
	docker compose run --rm ingest inspect
