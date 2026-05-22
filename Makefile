.PHONY: setup dev test lint

setup:
	cd backend && python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"

dev:
	cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000

test:
	cd backend && .venv/bin/pytest -q

lint:
	cd backend && .venv/bin/ruff check app tests
