.PHONY: setup dev test lint frontend frontend-dev frontend-build

setup:
	cd backend && python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"

dev:
	cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000

test:
	cd backend && .venv/bin/pytest -q

lint:
	cd backend && .venv/bin/ruff check app tests

frontend:
	cd frontend && npm install

frontend-dev:
	cd frontend && npm run dev

frontend-build:
	cd frontend && npm run build
