# DB Query Tool (W2)

Database query tool for PostgreSQL/MySQL with:

- Connection management and schema browsing
- Read-only SQL execution (`SELECT` only)
- Natural language to SQL generation (DeepSeek-compatible, dialect-aware)
- Local persistence for connection metadata

## Monorepo Structure

```text
w2/db_query/
├── backend/     # FastAPI service
├── frontend/    # React + TypeScript UI
├── fixtures/    # REST/curl test fixtures
└── Makefile
```

## Quick Start

```bash
cd w2/db_query
make backend-dev
make frontend-dev
```

- Backend: `http://127.0.0.1:8000`
- Frontend: `http://127.0.0.1:5173`

## API Health Checks

- `GET /health` -> backend service health
- `GET /health/llm` -> DeepSeek connectivity probe

## Core Constitution Constraints

- No authentication/authorization (intentional scope)
- CORS allows all origins (trusted/local environment)
- Backend JSON responses use camelCase
- SQL safety rules:
  - only `SELECT`
  - single statement only
  - default `LIMIT 1000` when missing
- Durable local state at `~/.db_query/db_query.db` (SQLite)
- API keys must come from environment variables and must not be persisted

## Phase 4 Verification Checklist

- [x] Backend README completed (`w2/db_query/backend/README.md`)
- [x] Frontend README completed (`w2/db_query/frontend/README.md`)
- [x] Project overview README updated (`w2/db_query/README.md`)
- [x] Type checking commands executed
- [x] Lint commands executed
- [x] Constitution principles re-verified against implementation

## Pointers

- Constitution: `.specify/memory/constitution.md`
- Feature docs: `specs/002-db-query-tool/`
