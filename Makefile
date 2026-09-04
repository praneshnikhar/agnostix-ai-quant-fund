# =============================================================================
# AI Quant Fund — Developer Makefile (M0)
# Windows note: use Git Bash / WSL for `make`, or run the underlying commands
# directly (see DEVELOPMENT.md).
# =============================================================================

.PHONY: dev build test lint format typecheck migrate seed down verify

# Use the project's Python 3.12 venv so `make` works regardless of the active
# shell environment (e.g. a conda base env on Python 3.10). Override with:
#   make migrate PY=python3.12
PY ?= .venv/bin/python

dev:
	docker compose up --build

build:
	docker compose build

test:
	$(PY) -m pytest apps/api/tests tests/integration -v

lint:
	$(PY) -m ruff check apps/api services
	$(PY) -m mypy apps/api/app services --ignore-missing-imports || true

format:
	$(PY) -m ruff format apps/api services
	$(PY) -m ruff check --fix apps/api services

typecheck:
	cd apps/web && npx tsc --noEmit

migrate:
	$(PY) -m alembic upgrade head

seed:
	$(PY) -m db.seeds.seed

down:
	docker compose down

verify: lint test
	@echo "M0 verification complete."