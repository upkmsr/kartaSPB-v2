.PHONY: up down migrate backend-test backend-quality frontend-test frontend-quality check

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
