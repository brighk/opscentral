.PHONY: dev-backend dev-frontend dev-agent db-up db-down db-migrate db-revision test test-backend test-frontend install

# Infrastructure
db-up:
	docker compose up -d

db-down:
	docker compose down

# Backend
install-backend:
	cd backend && pip install -e ".[dev]"

dev-backend:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

db-migrate:
	cd backend && alembic upgrade head

db-revision:
	cd backend && alembic revision --autogenerate -m "$(msg)"

test-backend:
	cd backend && pytest tests/ -v

# Frontend
install-frontend:
	cd frontend && npm install

dev-frontend:
	cd frontend && npm run dev

test-frontend:
	cd frontend && npm test

# Agent
install-agent:
	cd agent && pip install -e ".[dev]"

dev-agent:
	cd agent && python -m opscentral_agent.main

# Celery
dev-celery:
	cd backend && celery -A app.tasks.celery_app worker --loglevel=info

dev-celery-beat:
	cd backend && celery -A app.tasks.celery_app beat --loglevel=info

# All
install: install-backend install-frontend install-agent

test: test-backend
