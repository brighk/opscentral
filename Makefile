.PHONY: install install-backend install-frontend install-agent install-hooks \
	dev-backend dev-frontend dev-agent dev-celery dev-celery-beat \
	db-up db-down db-migrate db-revision \
	lint test test-backend

# Infrastructure
db-up:
	docker compose up -d

db-down:
	docker compose down

# Backend
install-backend:
	cd backend && uv sync

dev-backend:
	cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

db-migrate:
	cd backend && uv run alembic upgrade head

db-revision:
	cd backend && uv run alembic revision --autogenerate -m "$(msg)"

test-backend:
	cd backend && uv run pytest -v

# Frontend
install-frontend:
	cd frontend && npm ci

dev-frontend:
	cd frontend && npm run dev

# Agent
install-agent:
	cd agent && uv sync

dev-agent:
	cd agent && uv run python -m opscentral_agent.main

# Celery
dev-celery:
	cd backend && uv run celery -A app.tasks.celery_app worker --loglevel=info

dev-celery-beat:
	cd backend && uv run celery -A app.tasks.celery_app beat --loglevel=info

# Git hooks (run through uv, so ~/.local/bin doesn't need to be on PATH)
install-hooks:
	uv tool install pre-commit
	uv tool run pre-commit install

# All
install: install-backend install-frontend install-agent install-hooks

lint:
	uv tool run pre-commit run --all-files

test: test-backend
