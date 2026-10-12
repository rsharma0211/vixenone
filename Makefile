.PHONY: help up down logs seed reset migrate db-shell test types lint

help:
	@echo "Available commands:"
	@echo "  make up        - Build and start full stack (postgres, auth emulator, api, web)"
	@echo "  make down      - Gracefully stop full stack (persists emulator and db data)"
	@echo "  make logs      - Follow container logs"
	@echo "  make seed      - Seed demo user (demo@vixenone.app / demo1234) into Auth emulator"
	@echo "  make reset     - Stop stack, wipe db volume, emulator data & uploads, start fresh"
	@echo "  make migrate   - Run Alembic database migrations"
	@echo "  make db-shell  - Open psql shell inside postgres container"
	@echo "  make test      - Run backend unit tests inside api container"
	@echo "  make types     - Generate frontend types from OpenAPI schema"
	@echo "  make lint      - Run basic lint/syntax checks"

up:
	@mkdir -p emulator-data uploads
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f

seed:
	@python3 scripts/seed.py

reset:
	docker compose down -v
	rm -rf emulator-data uploads
	mkdir -p emulator-data uploads
	docker compose up -d --build

migrate:
	docker compose exec -T api alembic upgrade head

db-shell:
	docker compose exec postgres psql -U vixenone -d vixenone

test:
	@if docker compose ps --services --filter "status=running" | grep -q "^api$$"; then \
		docker compose exec -T api pytest tests; \
	else \
		docker compose run --rm -T api pytest tests; \
	fi

types:
	docker compose exec -T web npx --no-install openapi-typescript http://api:8000/api/openapi.json -o src/lib/types/schema.ts

lint:
	@echo "Linting backend and frontend..."
