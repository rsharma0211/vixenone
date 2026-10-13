.PHONY: help up down logs seed prepare reset migrate db-shell test types lint lint-api type-check type-check-api cloud-login cloud-config cloud-check

help:
	@echo "Available commands:"
	@echo "  make up          - Build and start full stack (postgres, auth emulator, api, web)"
	@echo "  make down        - Gracefully stop full stack (persists emulator and db data)"
	@echo "  make logs        - Follow container logs"
	@echo "  make seed        - Seed demo user (demo@vixenone.app / demo1234) into Auth emulator"
	@echo "  make reset       - Stop stack, wipe db volume, emulator data & uploads, start fresh"
	@echo "  make migrate     - Run Alembic database migrations"
	@echo "  make db-shell    - Open psql shell inside postgres container"
	@echo "  make test        - Run backend unit tests inside api container"
	@echo "  make types       - Generate frontend types from OpenAPI schema"
	@echo "  make lint        - Run basic lint/syntax checks"
	@echo "  make cloud-login  - Authenticate gcloud, ADC, and Firebase via interactive terminal"
	@echo "  make cloud-config - Set gcloud project (vixenone) and region (asia-south1)"
	@echo "  make cloud-check  - Verify active account, project, Cloud SQL, buckets, secrets, and Firebase"

up:
	@mkdir -p emulator-data uploads
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f

seed:
	@if docker compose ps --services --filter "status=running" | grep -q "^api$$"; then \
		docker compose exec -T api python -m app.cli.seed; \
	else \
		docker compose run --rm -T api python -m app.cli.seed; \
	fi

prepare:
	@if docker compose ps --services --filter "status=running" | grep -q "^api$$"; then \
		docker compose exec -T api python -m app.cli.prepare; \
	else \
		docker compose run --rm -T api prepare; \
	fi

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

lint: lint-api

lint-api:
	@if docker compose ps --services --filter "status=running" | grep -q "^api$$"; then \
		docker compose exec -T api ruff check app tests; \
	else \
		docker compose run --rm -T api ruff check app tests; \
	fi

type-check: type-check-api

type-check-api:
	@if docker compose ps --services --filter "status=running" | grep -q "^api$$"; then \
		docker compose exec -T api mypy app; \
	else \
		docker compose run --rm -T api mypy app; \
	fi

cloud-login:
	./scripts/cloud-tools.sh gcloud auth login --no-launch-browser
	./scripts/cloud-tools.sh gcloud auth application-default login --no-launch-browser
	./scripts/cloud-tools.sh firebase login --no-localhost

cloud-config:
	./scripts/cloud-tools.sh gcloud config set project vixenone
	./scripts/cloud-tools.sh gcloud config set compute/region asia-south1

cloud-check:
	@echo "=== Active Account ==="
	@./scripts/cloud-tools.sh gcloud auth list --filter=status:ACTIVE
	@echo ""
	@echo "=== Active Project ==="
	@./scripts/cloud-tools.sh gcloud config get-value project
	@echo ""
	@echo "=== Cloud SQL Instances ==="
	@./scripts/cloud-tools.sh gcloud sql instances list
	@echo ""
	@echo "=== Cloud Storage Buckets ==="
	@./scripts/cloud-tools.sh gcloud storage buckets list
	@echo ""
	@echo "=== Secrets ==="
	@./scripts/cloud-tools.sh gcloud secrets list
	@echo ""
	@echo "=== Firebase Projects ==="
	@./scripts/cloud-tools.sh firebase projects:list
