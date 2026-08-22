# =============================================================================
# AI Quant Fund — Developer Makefile (M0)
# Windows note: use Git Bash / WSL for `make`, or run the underlying commands
# directly (see DEVELOPMENT.md).
# =============================================================================

.PHONY: dev build test lint format typecheck migrate seed down verify

dev:
	docker compose up --build

build:
	docker compose build

test:
	pytest apps/api/tests tests/integration -v

lint:
	ruff check apps/api services
	mypy apps/api/app services --ignore-missing-imports || true

format:
	ruff format apps/api services
	ruff check --fix apps/api services

typecheck:
	cd apps/web && npx tsc --noEmit

migrate:
	alembic upgrade head

seed:
	python -m db.seeds.seed

down:
	docker compose down

verify: lint test
	@echo "M0 verification complete."