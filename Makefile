COMPOSE_FILE := infra/compose/docker-compose.yml
COMPOSE := docker compose -f $(COMPOSE_FILE)
API_DIR := apps/api

.PHONY: help bootstrap up down logs ps migrate seed assess test lint fmt api-shell db-shell ci evidence connectors-test

help:
	@echo "Phase 0 targets:"
	@echo "  make bootstrap  - copy .env, install API deps"
	@echo "  make up         - start local stack"
	@echo "  make down       - stop stack (keep volumes)"
	@echo "  make migrate    - run Alembic migrations"
	@echo "  make seed       - seed source registry"
	@echo "  make test       - run API tests"
	@echo "  make lint       - ruff + mypy (API)"
	@echo "  make ci         - local CI approximation"

bootstrap:
	@test -f .env || cp .env.example .env
	cd $(API_DIR) && uv sync --all-extras
	@echo "Bootstrap complete. Run: make up && make migrate && make seed"

up:
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

ps:
	$(COMPOSE) ps

migrate:
	cd $(API_DIR) && uv run alembic upgrade head

seed:
	cd $(API_DIR) && uv run python -m app.db.seed

assess:
	cd $(API_DIR) && uv run python -m app.db.run_assessments

test:
	cd $(API_DIR) && uv run pytest -q

connectors-test:
	cd packages/connectors && uv run pytest -q

lint:
	cd $(API_DIR) && uv run ruff check . && uv run mypy app

fmt:
	cd $(API_DIR) && uv run ruff format .

api-shell:
	$(COMPOSE) exec api bash

db-shell:
	$(COMPOSE) exec postgres psql -U newsfetcher -d newsfetcher

ci: lint connectors-test test

evidence:
	@echo "Commit: $$(git rev-parse HEAD 2>/dev/null || echo none)"
	@echo "Branch: $$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo none)"
