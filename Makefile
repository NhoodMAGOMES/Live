.PHONY: dev test seed migrate backend-test web-install

dev:
	docker compose up --build

migrate:
	docker compose run --rm api alembic upgrade head

seed:
	docker compose run --rm api python -m app.scripts.seed

test:
	docker compose run --rm api pytest

backend-test:
	cd backend && pytest

web-install:
	cd web && npm install

