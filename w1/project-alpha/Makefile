.PHONY: backend-install backend-lint backend-format backend-test backend-test-performance
.PHONY: backend-db-upgrade backend-db-downgrade backend-db-seed backend-dev
.PHONY: frontend-install frontend-lint frontend-format frontend-build frontend-test frontend-e2e frontend-dev
.PHONY: lint format test

backend-install:
	cd backend && pip install -e ".[dev]"

backend-lint:
	cd backend && ruff check .

backend-format:
	cd backend && ruff format .

backend-test:
	cd backend && pytest

backend-test-performance:
	cd backend && pytest -q tests/test_ticket_list_performance.py

backend-db-upgrade:
	cd backend && alembic -c alembic.ini upgrade head

backend-db-downgrade:
	cd backend && alembic -c alembic.ini downgrade -1

backend-db-seed:
	python backend/scripts/seed_db.py

backend-dev:
	cd backend && uvicorn app.main:app --reload --port 8000

frontend-install:
	cd frontend && npm install

frontend-lint:
	cd frontend && npm run lint

frontend-format:
	cd frontend && npm run format

frontend-build:
	cd frontend && npm run build

frontend-test:
	cd frontend && npm run test:run

frontend-e2e:
	cd frontend && npm run e2e

frontend-dev:
	cd frontend && npm run dev

lint: backend-lint frontend-lint

format: backend-format frontend-format

test: backend-test
