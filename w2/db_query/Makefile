BACKEND_DIR := backend
FRONTEND_DIR := frontend
BACKEND_PY := .\\.venv\\Scripts\\python.exe

.PHONY: help install backend-install frontend-install backend-dev frontend-dev typecheck backend-typecheck frontend-typecheck lint backend-lint frontend-lint test backend-test build frontend-build backend-compile

help:
	@echo Available targets:
	@echo   make install            - install backend and frontend dependencies
	@echo   make backend-install    - install backend dependencies with uv
	@echo   make frontend-install   - install frontend dependencies with npm
	@echo   make backend-dev        - run FastAPI dev server on :8000
	@echo   make frontend-dev       - run Vite dev server
	@echo   make typecheck          - run backend + frontend type checks
	@echo   make lint               - run backend + frontend lint
	@echo   make test               - run backend tests
	@echo   make build              - run frontend build + backend compile check

install: backend-install frontend-install

backend-install:
	cd $(BACKEND_DIR) && uv sync --no-install-project

frontend-install:
	cd $(FRONTEND_DIR) && npm install --no-audit --no-fund

backend-dev:
	cd $(BACKEND_DIR) && $(BACKEND_PY) -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

frontend-dev:
	cd $(FRONTEND_DIR) && npm run dev

typecheck: backend-typecheck frontend-typecheck

backend-typecheck:
	cd $(BACKEND_DIR) && $(BACKEND_PY) -m mypy src

frontend-typecheck:
	cd $(FRONTEND_DIR) && npm run type-check

lint: backend-lint frontend-lint

backend-lint:
	cd $(BACKEND_DIR) && $(BACKEND_PY) -m ruff check src tests

frontend-lint:
	cd $(FRONTEND_DIR) && npm run lint

test: backend-test

backend-test:
	powershell.exe -NoProfile -Command "cd '$(BACKEND_DIR)'; & '$(BACKEND_PY)' -m pytest; if ($$LASTEXITCODE -eq 5) { Write-Host 'No tests collected; treating as success.'; exit 0 } else { exit $$LASTEXITCODE }"

build: frontend-build backend-compile

frontend-build:
	cd $(FRONTEND_DIR) && npm run build

backend-compile:
	cd $(BACKEND_DIR) && $(BACKEND_PY) -m compileall -q src
